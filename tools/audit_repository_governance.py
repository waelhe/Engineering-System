#!/usr/bin/env python3
"""Read-only audit of repository main-branch rulesets against the PEOS policy."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "registry" / "peos" / "repository-governance.json"
API = "https://api.github.com"
API_VERSION = "2022-11-28"


class GovernanceAuditError(RuntimeError):
    pass


class GovernanceApiError(GovernanceAuditError):
    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub API HTTP {status}: {message}")
        self.status = status
        self.message = message


def api_get(path: str, token: str) -> Any:
    request = urllib.request.Request(
        API + path,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "peos-repository-governance-audit",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read(2000).decode("utf-8", errors="replace")
        raise GovernanceApiError(exc.code, detail) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GovernanceAuditError(f"GitHub API read failed for {path}: {exc}") from exc


def load_policy(path: Path) -> dict[str, Any]:
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceAuditError(f"Cannot read governance policy: {exc}") from exc
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise GovernanceAuditError("Governance policy must be a JSON object with schema_version=1")
    repositories = policy.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise GovernanceAuditError("Governance policy repositories must be a non-empty array")
    names: set[str] = set()
    for index, item in enumerate(repositories):
        if not isinstance(item, dict):
            raise GovernanceAuditError(f"repositories[{index}] must be an object")
        repository = item.get("repository")
        branch = item.get("default_branch")
        expected = item.get("expected")
        if not isinstance(repository, str) or repository.count("/") != 1:
            raise GovernanceAuditError(f"repositories[{index}].repository must use owner/repository form")
        if repository.lower() in names:
            raise GovernanceAuditError(f"Duplicate repository policy: {repository}")
        names.add(repository.lower())
        if not isinstance(branch, str) or not branch:
            raise GovernanceAuditError(f"repositories[{index}].default_branch is required")
        if not isinstance(expected, dict):
            raise GovernanceAuditError(f"repositories[{index}].expected must be an object")
        if not isinstance(expected.get("required_rules"), list):
            raise GovernanceAuditError(f"repositories[{index}].expected.required_rules must be an array")
        if not isinstance(expected.get("required_status_checks"), list):
            raise GovernanceAuditError(f"repositories[{index}].expected.required_status_checks must be an array")
    return policy


def targets_branch(ruleset: dict[str, Any], branch: str) -> bool:
    conditions = ruleset.get("conditions") or {}
    ref_name = conditions.get("ref_name") or {}
    includes = ref_name.get("include") or []
    excludes = ref_name.get("exclude") or []
    target = f"refs/heads/{branch}"
    matched = any(value in {target, "~DEFAULT_BRANCH", "~ALL"} for value in includes)
    excluded = any(value in {target, "~DEFAULT_BRANCH", "~ALL"} for value in excludes)
    return matched and not excluded


def audit_repository(repository_policy: dict[str, Any], token: str) -> dict[str, Any]:
    repository = repository_policy["repository"]
    branch = repository_policy["default_branch"]
    expected = repository_policy["expected"]
    encoded_branch = urllib.parse.quote(branch, safe="")
    branch_data = api_get(f"/repos/{repository}/branches/{encoded_branch}", token)
    branch_protected = bool(branch_data.get("protected"))

    try:
        rulesets = api_get(f"/repos/{repository}/rulesets?includes_parents=true", token)
    except GovernanceApiError as exc:
        if exc.status == 403 and (
            "Upgrade to GitHub Pro" in exc.message
            or "make this repository public" in exc.message
        ):
            return {
                "repository": repository,
                "branch": branch,
                "branch_protected": branch_protected,
                "status": "plan_limited",
                "reason": "GitHub plan does not expose repository rulesets for this private repository",
                "missing_rules": [],
                "missing_status_checks": [],
                "active_rulesets": [],
            }
        raise

    if not isinstance(rulesets, list):
        raise GovernanceAuditError(f"{repository}: rulesets endpoint returned a non-array response")

    matching: list[dict[str, Any]] = []
    for listed in rulesets:
        if (
            not isinstance(listed, dict)
            or listed.get("target") != "branch"
            or listed.get("enforcement") != "active"
        ):
            continue
        detail = api_get(f"/repos/{repository}/rulesets/{listed['id']}", token)
        if isinstance(detail, dict) and targets_branch(detail, branch):
            matching.append(detail)

    if not matching:
        if branch_protected:
            status = "protected_but_details_unavailable"
            reason = "Branch API reports protection, but no matching active repository/parent ruleset was readable; classic protection details need an admin-scoped audit."
        else:
            status = "policy_gap"
            reason = "No active repository or inherited branch ruleset applies to the default branch."
        return {
            "repository": repository,
            "branch": branch,
            "branch_protected": branch_protected,
            "status": status,
            "reason": reason,
            "missing_rules": list(expected["required_rules"]),
            "missing_status_checks": list(expected["required_status_checks"]),
            "active_rulesets": [],
        }

    rule_types: set[str] = set()
    required_contexts: set[str] = set()
    pull_request_parameters: list[dict[str, Any]] = []
    merge_methods: set[str] = set()
    for ruleset in matching:
        for rule in ruleset.get("rules") or []:
            if not isinstance(rule, dict) or not isinstance(rule.get("type"), str):
                continue
            rule_types.add(rule["type"])
            parameters = rule.get("parameters") or {}
            if rule["type"] == "required_status_checks":
                for check in parameters.get("required_status_checks") or []:
                    if isinstance(check, dict) and isinstance(check.get("context"), str):
                        required_contexts.add(check["context"])
            elif rule["type"] == "pull_request":
                pull_request_parameters.append(parameters)
                merge_methods.update(parameters.get("allowed_merge_methods") or [])

    missing_rules = sorted(set(expected["required_rules"]) - rule_types)
    missing_status_checks = sorted(set(expected["required_status_checks"]) - required_contexts)

    if "pull_request" in expected["required_rules"]:
        if not pull_request_parameters:
            missing_rules.append("pull_request")
        else:
            if not any(
                parameters.get("required_review_thread_resolution") is True
                for parameters in pull_request_parameters
            ):
                missing_rules.append("pull_request.thread_resolution")
            expected_approvals = expected.get("required_approving_review_count")
            if expected_approvals is not None and not any(
                parameters.get("required_approving_review_count") == expected_approvals
                for parameters in pull_request_parameters
            ):
                missing_rules.append("pull_request.approving_review_count")
            expected_merge_methods = set(expected.get("required_merge_methods") or [])
            if expected_merge_methods and not expected_merge_methods.issubset(merge_methods):
                missing_rules.append("pull_request.merge_methods")

    if any(ruleset.get("bypass_actors") for ruleset in matching):
        missing_rules.append("bypass_actors")
    if any(ruleset.get("current_user_can_bypass") not in {None, "never"} for ruleset in matching):
        missing_rules.append("current_user_can_bypass")
    missing_rules = sorted(set(missing_rules))
    status = "verified" if not missing_rules and not missing_status_checks else "policy_gap"
    return {
        "repository": repository,
        "branch": branch,
        "branch_protected": branch_protected,
        "status": status,
        "active_rulesets": [
            {"id": item.get("id"), "name": item.get("name"), "source": item.get("source")}
            for item in matching
        ],
        "observed_rules": sorted(rule_types),
        "observed_status_checks": sorted(required_contexts),
        "missing_rules": missing_rules,
        "missing_status_checks": missing_status_checks,
    }


def write_summary(report: dict[str, Any]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "# PEOS repository governance audit",
        "",
        "| Repository | Default branch | Result | Missing rules / checks |",
        "|---|---|---|---|",
    ]
    for result in report["results"]:
        gaps = ", ".join(result.get("missing_rules", []) + result.get("missing_status_checks", []))
        if result["status"] == "plan_limited":
            gaps = result.get("reason", "Plan-limited")
        elif not gaps:
            gaps = "—"
        lines.append(
            f"| {result['repository']} | {result['branch']} | {result['status']} | {gaps} |"
        )
    lines.extend([
        "",
        "This audit is read-only. It does not create, update or delete rulesets.",
        "A plan-limited repository is unknown, not verified and not evidence of an absent ruleset.",
    ])
    with Path(summary_path).open("a", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN is required for read-only repository governance auditing", file=sys.stderr)
        return 2
    try:
        policy = load_policy(args.config)
        results = [audit_repository(item, token) for item in policy["repositories"]]
        report = {
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "policy_snapshot_date": policy.get("snapshot_date"),
            "results": results,
            "summary": {
                "verified": sum(item["status"] == "verified" for item in results),
                "policy_gaps": sum(item["status"] == "policy_gap" for item in results),
                "plan_limited": sum(item["status"] == "plan_limited" for item in results),
                "protected_details_unavailable": sum(
                    item["status"] == "protected_but_details_unavailable" for item in results
                ),
            },
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        write_summary(report)
        return 1 if report["summary"]["policy_gaps"] else 0
    except (GovernanceAuditError, OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
