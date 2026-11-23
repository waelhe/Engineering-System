#!/usr/bin/env python3
"""Collect source-linked reviews from registered repositories into the EGM inbox.

Source repositories are queried with a read-only GitHub App token. The canonical
Engineering-System repository is the only write target and uses the workflow's
separate GITHUB_TOKEN. No source PR branch or artifact is checked out or run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from tools.egm_knowledge import KnowledgeError
from tools.github_review_intake import (
    IntakeError,
    api_request,
    collect_one_pr,
    git,
    prepare_branch,
    publish_batch,
    recent_open_prs,
    run_trusted_python,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "registry" / "peos" / "review-sources.json"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def load_registry(path: Path) -> dict[str, Any]:
    """Load and strictly validate the source/sink registry before using tokens."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntakeError(f"Cannot read cross-repository source registry: {exc}") from exc

    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise IntakeError("Cross-repository source registry must have schema_version=1")
    sink = value.get("sink_repository")
    if not isinstance(sink, str) or not REPOSITORY_PATTERN.fullmatch(sink):
        raise IntakeError("sink_repository must use owner/repository form")

    sources = value.get("repositories")
    if not isinstance(sources, list) or not sources:
        raise IntakeError("repositories must be a non-empty array")

    seen_repositories: set[str] = set()
    seen_projects: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise IntakeError(f"repositories[{index}] must be an object")
        repository = source.get("repository")
        project_id = source.get("project_id")
        default_branch = source.get("default_branch")
        enabled = source.get("enabled")
        since_days = source.get("since_days")
        max_prs = source.get("max_prs")

        if not isinstance(repository, str) or not REPOSITORY_PATTERN.fullmatch(repository):
            raise IntakeError(f"repositories[{index}].repository must use owner/repository form")
        if repository.lower() == sink.lower():
            raise IntakeError("The sink repository must not also be configured as a source")
        if repository.lower() in seen_repositories:
            raise IntakeError(f"Duplicate source repository: {repository}")
        if not isinstance(project_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,79}", project_id):
            raise IntakeError(f"repositories[{index}].project_id is invalid")
        if project_id in seen_projects:
            raise IntakeError(f"Duplicate source project_id: {project_id}")
        if not isinstance(default_branch, str) or not default_branch.strip():
            raise IntakeError(f"repositories[{index}].default_branch is required")
        if not isinstance(enabled, bool):
            raise IntakeError(f"repositories[{index}].enabled must be boolean")
        if type(since_days) is not int or not 1 <= since_days <= 90:
            raise IntakeError(f"repositories[{index}].since_days must be 1..90")
        if type(max_prs) is not int or not 1 <= max_prs <= 100:
            raise IntakeError(f"repositories[{index}].max_prs must be 1..100")

        seen_repositories.add(repository.lower())
        seen_projects.add(project_id)
        normalized.append({
            "repository": repository,
            "project_id": project_id,
            "default_branch": default_branch,
            "enabled": enabled,
            "since_days": since_days,
            "max_prs": max_prs,
        })

    return {"sink_repository": sink, "repositories": normalized}


def collect_source_repository(
    source: dict[str, Any],
    source_token: str,
    event_action: str,
) -> dict[str, Any]:
    """Capture recent open PR reviews/comments only for the source default branch."""
    repository = source["repository"]
    metadata = api_request("GET", f"/repos/{repository}", source_token)
    actual_default = metadata.get("default_branch")
    if actual_default != source["default_branch"]:
        raise IntakeError(
            f"{repository}: configured default branch {source['default_branch']!r} "
            f"does not match GitHub's current default branch {actual_default!r}"
        )

    candidates = recent_open_prs(
        repository,
        source_token,
        source["since_days"],
        source["max_prs"],
    )
    selected: list[int] = []
    skipped_other_base: list[int] = []
    for number in candidates:
        pr = api_request("GET", f"/repos/{repository}/pulls/{number}", source_token)
        if (pr.get("base") or {}).get("repo", {}).get("full_name", "").lower() != repository.lower():
            raise IntakeError(f"{repository} PR #{number} does not have the registered base repository")
        if (pr.get("base") or {}).get("ref") != actual_default:
            skipped_other_base.append(number)
            continue
        selected.append(number)

    totals = {"created": 0, "duplicate": 0, "objects": 0, "prs": 0}
    for number in selected:
        counts = collect_one_pr(
            repository,
            source["project_id"],
            source_token,
            number,
            event_action,
        )
        totals["prs"] += 1
        for key in ("created", "duplicate", "objects"):
            totals[key] += counts.get(key, 0)

    return {
        "repository": repository,
        "project_id": source["project_id"],
        "selected_prs": selected,
        "skipped_non_default_base_prs": skipped_other_base,
        **totals,
    }


def validate_knowledge() -> None:
    """Run trusted main-branch validators without carrying API credentials."""
    run_trusted_python("tools/egm_knowledge.py", "validate")
    run_trusted_python("tools/validate_migration.py")
    run_trusted_python("tools/egm_knowledge.py", "index")
    run_trusted_python("tools/egm_knowledge.py", "validate-receipts")
    run_trusted_python("tools/peos_validate.py")
    run_trusted_python("-m", "pytest", "-q")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--event-action", default="scheduled_cross_repository_scan")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    args = parser.parse_args(argv)

    sink_repository = os.environ.get("GITHUB_REPOSITORY", "")
    source_token = os.environ.get("EGM_SOURCE_GITHUB_TOKEN", "")
    sink_token = os.environ.get("GITHUB_TOKEN", "")
    if not sink_repository or not sink_token:
        print("GITHUB_REPOSITORY and GITHUB_TOKEN are required for the canonical sink", file=sys.stderr)
        return 2
    if not source_token:
        print(
            "Cross-repository intake is disabled: configure the read-only "
            "EGM_SOURCE_GITHUB_TOKEN generated from the registered GitHub App.",
            file=sys.stderr,
        )
        return 2
    if not args.run_id.isdigit() or not args.run_attempt.isdigit():
        print("GITHUB_RUN_ID and GITHUB_RUN_ATTEMPT must be numeric", file=sys.stderr)
        return 2

    try:
        registry = load_registry(args.source_config)
        if sink_repository.lower() != registry["sink_repository"].lower():
            raise IntakeError(
                f"Workflow sink {sink_repository!r} does not match registry sink "
                f"{registry['sink_repository']!r}"
            )

        summaries = []
        enabled_sources = [source for source in registry["repositories"] if source["enabled"]]
        if not enabled_sources:
            print(json.dumps({"message": "No source repositories are enabled; no changes made."}))
            return 0

        for source in enabled_sources:
            summaries.append(collect_source_repository(source, source_token, args.event_action))

        created = sum(item["created"] for item in summaries)
        objects = sum(item["objects"] for item in summaries)
        if created == 0:
            print(json.dumps({
                "message": "No new source Signals; no intake branch or PR created.",
                "sources": summaries,
            }, ensure_ascii=False))
            return 0

        # These validations and Git writes execute trusted sink-branch code only.
        validate_knowledge()
        branch, base_branch = prepare_branch(
            registry["sink_repository"], sink_token, args.run_id, args.run_attempt
        )
        publication = publish_batch(
            registry["sink_repository"], sink_token, branch, base_branch
        )
        print(json.dumps({
            "sink_repository": registry["sink_repository"],
            "source_repository_count": len(enabled_sources),
            "source_object_count": objects,
            "new_signal_count": created,
            "sources": summaries,
            "publication": publication,
        }, ensure_ascii=False))
        return 0
    except (IntakeError, KnowledgeError, OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
