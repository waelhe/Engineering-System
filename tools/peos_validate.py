"""Validate the checked-in PEOS W0 evidence snapshots.

This is a deterministic consistency validator, not a live GitHub client.
The registry files are point-in-time observations bound to repository SHAs.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc


def validate_registry(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    schema_path = root / "schemas" / "peos-inventory.schema.json"
    try:
        schema = read_json(schema_path)
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return [f"invalid PEOS schema: {exc}"]

    expected = {
        "modules": ("module_registry", "app-java-v3.modules.json"),
        "journeys": ("journey_registry", "app-java-v3.journeys.json"),
        "prs": ("pull_request_registry", "app-java-v3.open-prs.json"),
    }
    loaded: dict[str, dict[str, Any]] = {}
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for key, (kind, filename) in expected.items():
        path = root / "registry" / "peos" / filename
        try:
            payload = read_json(path)
            found = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
            if found:
                details = "; ".join(
                    f"{'/'.join(map(str, item.absolute_path))}: {item.message}" for item in found
                )
                errors.append(f"{filename}: {details}")
                continue
            if payload.get("kind") != kind:
                errors.append(f"{filename}: expected kind {kind}")
            loaded[key] = payload
        except ValueError as exc:
            errors.append(str(exc))

    modules = loaded.get("modules", {}).get("records", [])
    module_ids = [item.get("module_id") for item in modules]
    if len(modules) != 30:
        errors.append(f"expected 30 Maven reactor modules, found {len(modules)}")
    if len(module_ids) != len(set(module_ids)):
        errors.append("module IDs are not unique")
    for item in modules:
        if item.get("membership") != "declared_in_root_maven_reactor":
            errors.append(f"{item.get('module_id')}: module membership is not source-backed")

    journeys = loaded.get("journeys", {}).get("records", [])
    journey_ids = [item.get("journey_id") for item in journeys]
    expected_ids = [f"J{i:02d}" for i in range(1, 36)]
    if sorted(journey_ids) != expected_ids:
        errors.append("journey IDs must be exactly J01..J35 with one canonical record each")
    if len(journey_ids) != len(set(journey_ids)):
        errors.append("canonical journey IDs are not unique")
    for item in journeys:
        if item.get("current_main_revalidation") != "not_revalidated_at_2026-11-14-main":
            errors.append(f"{item.get('journey_id')}: historic status must not be presented as current proof")
    journey_anomalies = loaded.get("journeys", {}).get("anomalies", [])
    if not any(item.get("id") == "W0-JOURNEY-001" for item in journey_anomalies):
        errors.append("journey source duplicate/boundary anomaly must remain visible")
    if not any(item.get("journey_id") == "J29" and item.get("source_occurrences") == 2 for item in journeys):
        errors.append("J29 source duplicate occurrence count must remain recorded")

    prs = loaded.get("prs", {}).get("records", [])
    pr_numbers = [item.get("number") for item in prs]
    if len(prs) != 23:
        errors.append(f"expected 23 open PRs in captured API page, found {len(prs)}")
    if len(pr_numbers) != len(set(pr_numbers)):
        errors.append("PR numbers are not unique")
    for item in prs:
        if not SHA_RE.fullmatch(item.get("head", {}).get("sha", "")):
            errors.append(f"PR #{item.get('number')}: invalid head SHA")
        if not SHA_RE.fullmatch(item.get("base", {}).get("sha", "")):
            errors.append(f"PR #{item.get('number')}: invalid base SHA")
        if item.get("allowed_to_merge") is not False:
            errors.append(f"PR #{item.get('number')}: W0 snapshot must not authorize merge")

    by_number = {item.get("number"): item for item in prs}
    candidate = by_number.get(787)
    if not candidate or candidate.get("merge_policy") != "release_candidate_not_mergeable":
        errors.append("PR #787 must remain the single non-mergeable commerce candidate")
    if candidate and candidate.get("mergeable_snapshot") is not False:
        errors.append("PR #787 mergeable state must be recorded as false")

    for number in range(806, 812):
        shard = by_number.get(number)
        if not shard or shard.get("merge_policy") != "tracking_only":
            errors.append(f"PR #{number} must remain a tracking-only review shard")

    stacked = by_number.get(837)
    candidate = by_number.get(787)
    if stacked and candidate:
        if stacked.get("base", {}).get("sha") != candidate.get("head", {}).get("sha"):
            errors.append("PR #837 must remain stacked on the measured #787 head")
        if stacked.get("base", {}).get("branch") != candidate.get("head", {}).get("branch"):
            errors.append("PR #837 base branch must match #787 candidate branch")

    project_path = root / "registry" / "peos" / "projects.json"
    try:
        project = read_json(project_path)
        backend = next(item for item in project["records"] if item["repository"] == "waelhe/app-java-v3")
        if backend["modules"] != len(modules):
            errors.append("project module count disagrees with module registry")
        if backend["main_sha"] != loaded.get("modules", {}).get("source", {}).get("commit_sha"):
            errors.append("project main SHA disagrees with module inventory source SHA")
    except (ValueError, KeyError, StopIteration, TypeError) as exc:
        errors.append(f"projects.json: {exc}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PEOS W0 inventory snapshots.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate_registry(args.root)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PEOS W0 registry validation: PASS")
    print("Validated 30 Maven modules, 35 canonical journeys and 23 open PRs.")
    print("Historic journey labels remain marked not-revalidated; no merge is authorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
