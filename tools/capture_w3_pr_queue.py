"""Read-only GitHub capture for the PEOS W3 pull-request queue.

This tool refreshes the W3 snapshot from GitHub REST API. It never changes PRs,
branches, repository settings or merge state. Writing the snapshot requires an
explicit --write flag.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

API = "https://api.github.com"
API_VERSION = "2022-11-28"
ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path("registry/peos/app-java-v3.w3-pr-queue.json")
REQUIRED_GOVERNED_PRS = {787, 806, 807, 808, 809, 810, 811, 837}


class CaptureError(RuntimeError):
    """Raised when GitHub evidence is incomplete or inconsistent."""


def api_get(path: str, token: str) -> Any:
    request = urllib.request.Request(
        API + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "peos-read-only-pr-queue-capture",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read(2000).decode("utf-8", errors="replace")
        raise CaptureError(f"GitHub API returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise CaptureError(f"GitHub API request failed: {exc}") from exc


def api_pages(path: str, token: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    page = 1
    while True:
        separator = "&" if "?" in path else "?"
        batch = api_get(f"{path}{separator}per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise CaptureError(f"Expected an array while reading {path}")
        records.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < 100:
            return records
        page += 1
        if page > 100:
            raise CaptureError(f"Pagination safety limit reached for {path}")


def _pr_record(pr: dict[str, Any], template: dict[str, Any] | None) -> dict[str, Any]:
    number = pr.get("number")
    if not isinstance(number, int) or number < 1:
        raise CaptureError("GitHub returned a PR without a valid number")
    base = pr.get("base") or {}
    head = pr.get("head") or {}
    base_repo = (base.get("repo") or {}).get("full_name")
    if not isinstance(base_repo, str):
        raise CaptureError(f"PR #{number} has no base repository identity")
    if not isinstance(base.get("sha"), str) or len(base["sha"]) != 40:
        raise CaptureError(f"PR #{number} has no exact base SHA")
    if not isinstance(head.get("sha"), str) or len(head["sha"]) != 40:
        raise CaptureError(f"PR #{number} has no exact head SHA")
    if pr.get("state") != "open":
        raise CaptureError(f"PR #{number} appeared in the open queue with state {pr.get('state')!r}")

    if template:
        category = template.get("category", "unclassified")
        merge_policy = template.get("merge_policy", "not_authorized_pending_adjudication")
        assessment = template.get("assessment", "Classification retained from the preceding governed snapshot.")
    else:
        category = "unclassified"
        merge_policy = "not_authorized_pending_adjudication"
        assessment = (
            "Newly discovered open PR. No automatic merge permission or domain classification; "
            "owner adjudication and exact-head review are required."
        )

    base_branch = base.get("ref")
    base_relation = (
        "base_matches_current_main"
        if base_branch == "main"
        else "non_main_base_requires_adjudication"
    )
    record = {
        "id": f"W3-PR-{number}",
        "pr_number": number,
        "title": str(pr.get("title") or f"PR #{number}"),
        "url": str(pr.get("html_url") or ""),
        "state": "open",
        "draft": bool(pr.get("draft", False)),
        "base_branch": base_branch,
        "base_sha": base["sha"],
        "head_branch": head.get("ref"),
        "head_sha": head["sha"],
        "head_repository": (head.get("repo") or {}).get("full_name"),
        "mergeable": pr.get("mergeable"),
        "changed_files": pr.get("changed_files"),
        "commit_count": pr.get("commits"),
        "updated_at": pr.get("updated_at"),
        "category": category,
        "merge_policy": merge_policy,
        "base_relation": base_relation,
        "observed_workflows": (
            "not_collected_by_w3_capture; check-run evidence is captured separately"
        ),
        "assessment": assessment,
    }
    return record


def build_snapshot(
    repository: str,
    main_sha: str,
    pulls: list[dict[str, Any]],
    previous: dict[str, Any],
    stacked_comparison: dict[str, Any] | None = None,
    snapshot_date: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic W3 snapshot from already captured GitHub API objects."""
    if len(main_sha) != 40 or any(char not in "0123456789abcdef" for char in main_sha):
        raise CaptureError("Default-branch commit SHA must be a full lowercase 40-character SHA")

    previous_records = {
        int(item["pr_number"]): item
        for item in previous.get("records", [])
        if isinstance(item.get("pr_number"), int)
    }
    records = []
    seen: set[int] = set()
    for pull in pulls:
        number = pull.get("number")
        if not isinstance(number, int):
            raise CaptureError("Open PR inventory contains an invalid PR number")
        base_repository = ((pull.get("base") or {}).get("repo") or {}).get("full_name")
        if not isinstance(base_repository, str) or base_repository.lower() != repository.lower():
            raise CaptureError(f"PR #{number} base repository does not match configured project {repository}")
        if number in seen:
            raise CaptureError(f"Duplicate PR #{number} in GitHub response")
        seen.add(number)
        records.append(_pr_record(pull, previous_records.get(number)))

    missing_governed = REQUIRED_GOVERNED_PRS - seen
    if missing_governed:
        raise CaptureError(
            "Governed PRs require an explicit human transition before W3 refresh: "
            + ", ".join(f"#{number}" for number in sorted(missing_governed))
        )

    records.sort(key=lambda item: item["pr_number"])
    by_number = {item["pr_number"]: item for item in records}
    candidate = by_number[787]
    for number in range(806, 812):
        by_number[number]["merge_policy"] = "tracking_only_do_not_merge"
        by_number[number]["category"] = "commerce_review_shard"
        by_number[number]["assessment"] = (
            f"Permanent review-coverage shard for PR #787; tracking only; DO NOT MERGE."
        )
    candidate["merge_policy"] = "single_full_commerce_candidate"
    candidate["category"] = "full_commerce_release"

    stacked = by_number[837]
    if stacked.get("base_branch") != candidate.get("head_branch"):
        raise CaptureError("PR #837 no longer targets the PR #787 candidate branch; adjudicate stack policy")
    if not isinstance(stacked_comparison, dict):
        raise CaptureError("GitHub Compare API evidence is required for stacked PR #837")
    comparison_status = stacked_comparison.get("status")
    ahead_by = stacked_comparison.get("ahead_by")
    behind_by = stacked_comparison.get("behind_by")
    if (
        comparison_status not in {"ahead", "identical"}
        or not isinstance(ahead_by, int)
        or not isinstance(behind_by, int)
        or behind_by != 0
        or (comparison_status == "ahead" and ahead_by <= 0)
        or (comparison_status == "identical" and ahead_by != 0)
    ):
        raise CaptureError("PR #837 base is not a verifiable ancestor of the current PR #787 head")
    stacked["base_relation"] = "stacked_base_behind_candidate" if ahead_by > 0 else "stacked_base_matches_candidate"
    stack_proof = {
        "number": 837,
        "base_branch": stacked["base_branch"],
        "base_sha": stacked["base_sha"],
        "candidate_pr": 787,
        "candidate_head_sha": candidate["head_sha"],
        "comparison_status": comparison_status,
        "ahead_by": ahead_by,
        "behind_by": behind_by,
        "compare_url": stacked_comparison.get("html_url") or stacked_comparison.get("url"),
    }

    return {
        "schema_version": 1,
        "kind": "w3_pr_queue_snapshot",
        "snapshot_date": snapshot_date or date.today().isoformat(),
        "sources": [{
            "system": "github",
            "repository": repository,
            "ref": "main",
            "commit_sha": main_sha,
            "capture_method": "Read-only GitHub REST API capture of repository, default-branch commit, open PRs and stacked-branch compare evidence.",
        }],
        "open_pr_count": len(records),
        "records": records,
        "special_rules": {
            "full_commerce_candidate_pr": 787,
            "tracking_only_shards": [806, 807, 808, 809, 810, 811],
            "stacked_prs": [stack_proof],
        },
        "anomalies": [
            "New PRs without a prior governed classification default to not_authorized_pending_adjudication.",
            "Governed PRs #787, #806-#811 and #837 must be explicitly adjudicated before removal or retargeting.",
        ],
        "assessment": (
            f"Read-only GitHub capture of {len(records)} currently open PRs. "
            "Merge policies are carried forward only for known PRs; new PRs are never auto-authorized."
        ),
    }


def capture(repository: str, token: str, previous: dict[str, Any]) -> dict[str, Any]:
    if not token:
        raise CaptureError("A read-only GitHub token is required in the configured environment variable")
    repo_info = api_get(f"/repos/{repository}", token)
    default_branch = repo_info.get("default_branch")
    if default_branch != "main":
        raise CaptureError(f"Expected governed default branch 'main', received {default_branch!r}")
    main_commit = api_get(f"/repos/{repository}/commits/{default_branch}", token)
    main_sha = (main_commit.get("sha") if isinstance(main_commit, dict) else None)
    pulls = api_pages(f"/repos/{repository}/pulls?state=open&sort=updated&direction=desc", token)
    detailed = [
        api_get(f"/repos/{repository}/pulls/{pull['number']}", token)
        for pull in pulls
        if isinstance(pull.get("number"), int)
    ]
    by_number = {item.get("number"): item for item in detailed}
    candidate = by_number.get(787) or {}
    stacked = by_number.get(837) or {}
    base_sha = (stacked.get("base") or {}).get("sha")
    candidate_head_sha = (candidate.get("head") or {}).get("sha")
    if not isinstance(base_sha, str) or not isinstance(candidate_head_sha, str):
        raise CaptureError("Could not resolve exact base/head SHAs for stacked PR #837 and candidate PR #787")
    comparison = api_get(
        f"/repos/{repository}/compare/{base_sha}...{candidate_head_sha}",
        token,
    )
    if not isinstance(main_sha, str):
        raise CaptureError("GitHub did not return the default-branch commit SHA")
    return build_snapshot(repository, main_sha, detailed, previous, comparison)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="waelhe/app-java-v3")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--check", action="store_true", help="fail if the checked-in snapshot differs; do not write")
    parser.add_argument("--write", action="store_true", help="replace the checked-in W3 snapshot")
    args = parser.parse_args(argv)
    if args.check and args.write:
        parser.error("--check and --write are mutually exclusive")
    path = args.root / REGISTRY
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        snapshot = capture(args.repository, os.environ.get(args.token_env, ""), previous)
        rendered = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
        current = path.read_text(encoding="utf-8")
        if args.check:
            if rendered != current:
                print("W3 PR queue snapshot is stale; run with --write to create a new measured capture.")
                return 1
            print("W3 PR queue snapshot: current")
            return 0
        if args.write:
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(rendered, encoding="utf-8")
            temporary.replace(path)
            print(f"Updated {path.relative_to(args.root)} with {snapshot['open_pr_count']} open PRs.")
            return 0
        print(rendered, end="")
        return 0
    except (OSError, json.JSONDecodeError, CaptureError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
