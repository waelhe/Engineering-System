"""Validate the checked-in PEOS evidence snapshots.

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
        "operations": ("operations_registry", "app-java-v3.operations.json"),
        "boundaries": ("module_boundaries_registry", "app-java-v3.module-boundaries.json"),
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

    boundaries = loaded.get("boundaries", {})
    boundary_records = boundaries.get("records", [])
    maven_records = boundaries.get("maven_modules", [])
    if boundaries.get("source", {}).get("commit_sha") != loaded.get("modules", {}).get("source", {}).get("commit_sha"):
        errors.append("W2 boundary registry source SHA disagrees with Maven module inventory")
    if boundaries.get("source", {}).get("commit_sha") != "8b1d2a82bf5c870d88ffc7d5d05e36bb06175c26":
        errors.append("W2 boundaries must remain bound to the audited backend main SHA")
    maven_ids = [item.get("module_id") for item in maven_records]
    if len(maven_records) != 30 or len(maven_ids) != len(set(maven_ids)):
        errors.append("W2 must contain exactly 30 unique Maven reactor modules")
    for item in maven_records:
        if not SHA_RE.fullmatch(item.get("pom_blob_sha", "")):
            errors.append(f"W2 {item.get('module_id')}: invalid POM blob SHA")
        for dependency in item.get("internal_maven_dependencies", []):
            if dependency not in set(maven_ids):
                errors.append(f"W2 {item.get('module_id')}: unknown internal Maven dependency {dependency}")
    logical_ids = [item.get("module_name") for item in boundary_records]
    if len(boundary_records) != 30 or len(logical_ids) != len(set(logical_ids)):
        errors.append("W2 must contain exactly 30 unique logical Modulith modules")
    logical_set = set(logical_ids)
    for item in boundary_records:
        if item.get("domain_ownership") != "not_adjudicated":
            errors.append(f"W2 {item.get('module_name')}: domain ownership must remain not_adjudicated")
        dec = item.get("declaration", {})
        if dec.get("placement") not in {"package_info", "type"} or not SHA_RE.fullmatch(dec.get("blob_sha", "")):
            errors.append(f"W2 {item.get('module_name')}: module declaration source evidence invalid")
        for dependency in item.get("allowed_dependencies", []):
            target = dependency.split(" :: ", 1)[0]
            if target not in logical_set:
                errors.append(f"W2 {item.get('module_name')}: unknown allowed Modulith dependency {dependency}")
    type_level = {item.get("module_name") for item in boundary_records if item.get("declaration", {}).get("placement") == "type"}
    if type_level != {"availability", "disputes", "ledger", "notifications", "provider"}:
        errors.append(f"W2 type-level declarations differ from source inventory: {sorted(type_level)}")
    by_maven = {item.get("module_id"): item for item in maven_records}
    if by_maven.get("marketplace-platform-infra", {}).get("modulith_modules") != ["shared"]:
        errors.append("W2 platform-infra must map to logical shared")
    if set(by_maven.get("marketplace-app", {}).get("modulith_modules", [])) != {"app", "admin", "config"}:
        errors.append("W2 marketplace-app must map to app/admin/config")
    edge = by_maven.get("marketplace-edge", {})
    if edge.get("modulith_modules") != [] or edge.get("reactor_role") != "standalone_edge_bff":
        errors.append("W2 edge must remain outside MarketplaceApplication Modulith verification")
    if len([item for item in boundary_records if item.get("logical_kind") == "bounded_context"]) != 26:
        errors.append("W2 bounded-context package count must be 26")

    # Validate the W2-specific JSON Schema, not only the common registry envelope.
    try:
        boundary_schema = read_json(root / "schemas" / "peos-module-boundaries.schema.json")
        Draft202012Validator.check_schema(boundary_schema)
        boundary_payload = loaded.get("boundaries", {})
        boundary_errors = list(Draft202012Validator(boundary_schema, format_checker=FormatChecker()).iter_errors(boundary_payload))
        for item in boundary_errors:
            errors.append(f"app-java-v3.module-boundaries.json: {'/'.join(map(str, item.absolute_path))}: {item.message}")
    except Exception as exc:
        errors.append(f"invalid W2 module-boundaries schema: {exc}")

    maven_by_id = {item.get("module_id"): item for item in maven_records}
    for item in boundary_records:
        for maven_id in item.get("maven_modules", []):
            if maven_id not in maven_by_id or item.get("module_name") not in maven_by_id[maven_id].get("modulith_modules", []):
                errors.append(f"W2 {item.get('module_name')}: inconsistent Maven mapping {maven_id}")
    for item in maven_records:
        for logical_id in item.get("modulith_modules", []):
            found = next((record for record in boundary_records if record.get("module_name") == logical_id), None)
            if found is None or item.get("module_id") not in found.get("maven_modules", []):
                errors.append(f"W2 {item.get('module_id')}: inconsistent Modulith mapping {logical_id}")

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

    operations = loaded.get("operations", {}).get("records", [])
    operation_ids = [item.get("id") for item in operations]
    required_operation_ids = {
        "OPS-RAILWAY-001", "OPS-RAILWAY-002", "OPS-GITHUB-001", "OPS-GITHUB-002",
        "OPS-REPO-001", "OPS-GRAFANA-001", "OPS-GRAFANA-002", "OPS-GRAFANA-003", "OPS-GRAFANA-004",
    }
    if len(operation_ids) != len(set(operation_ids)):
        errors.append("operations record IDs are not unique")
    missing_operations = required_operation_ids - set(operation_ids)
    if missing_operations:
        errors.append(f"operations evidence missing required records: {sorted(missing_operations)}")
    for item in operations:
        if not item.get("id") or not item.get("system") or not item.get("state"):
            errors.append("every operations record requires id, system and state")
        if not item.get("evidence"):
            errors.append(f"{item.get('id')}: operational state must cite at least one evidence item")
    by_operation = {item.get("id"): item for item in operations}
    expected_states = {
        "OPS-RAILWAY-001": "offline",
        "OPS-GRAFANA-001": "no_series",
        "OPS-GRAFANA-002": "incomplete_datasource_configuration",
        "OPS-GRAFANA-003": "no_alert_rules",
        "OPS-GRAFANA-004": "no_notification_destination",
        "OPS-GITHUB-002": "open_incident",
    }
    for record_id, expected_state in expected_states.items():
        if by_operation.get(record_id, {}).get("state") != expected_state:
            errors.append(f"{record_id}: state must remain explicitly {expected_state} until reverified")

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
    print("PEOS inventory validation: PASS")
    print("Validated 30 Maven artifacts, 30 logical Modulith modules, 35 canonical journeys, 23 historical PR records and W1 operational evidence.")
    print("Historic journey labels remain marked not-revalidated; Maven and Modulith graphs are distinct; no merge is authorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
