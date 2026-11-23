"""Validate the checked-in PEOS evidence snapshots.

This is a deterministic consistency validator, not a live GitHub client.
The registry files are point-in-time observations bound to repository SHAs.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
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


def validate_auxiliary_registries(root: Path = ROOT) -> list[str]:
    """Validate the source-review and repository-governance registries without network access."""
    errors: list[str] = []
    review_path = root / "registry" / "peos" / "review-sources.json"
    governance_path = root / "registry" / "peos" / "repository-governance.json"

    def contains_secret_key(value: Any, path: str = "$") -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in {"token", "private_key", "secret", "password", "access_token"}:
                    found.append(f"{path}.{key}")
                found.extend(contains_secret_key(item, f"{path}.{key}"))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                found.extend(contains_secret_key(item, f"{path}[{index}]"))
        return found

    try:
        review = read_json(review_path)
        if review.get("schema_version") != 1 or review.get("kind") != "trusted_review_source_registry":
            errors.append("review-sources.json: invalid schema_version or kind")
        sink = review.get("sink_repository")
        if sink != "waelhe/Engineering-System":
            errors.append("review-sources.json: sink must remain the canonical Engineering-System repository")
        sources = review.get("repositories")
        if not isinstance(sources, list) or not sources:
            errors.append("review-sources.json: repositories must be a non-empty array")
            sources = []
        project_map: dict[str, str] = {}
        profiles_dir = root / "knowledge" / "projects"
        if profiles_dir.exists():
            for profile_path in sorted(profiles_dir.glob("*.json")):
                try:
                    profile = read_json(profile_path)
                    project_id = profile.get("project_id")
                    for repository in profile.get("repositories", []):
                        if isinstance(project_id, str) and isinstance(repository, dict):
                            project_map[repository.get("name")] = project_id
                except ValueError as exc:
                    errors.append(str(exc))
        seen_repositories: set[str] = set()
        seen_projects: set[str] = set()
        for index, item in enumerate(sources):
            if not isinstance(item, dict):
                errors.append(f"review-sources.json: repositories[{index}] must be an object")
                continue
            repository = item.get("repository")
            project_id = item.get("project_id")
            if not isinstance(repository, str) or repository.count("/") != 1:
                errors.append(f"review-sources.json: repositories[{index}].repository is invalid")
                continue
            if repository.lower() == str(sink).lower():
                errors.append("review-sources.json: sink repository cannot be a source")
            if repository.lower() in seen_repositories:
                errors.append(f"review-sources.json: duplicate source repository {repository}")
            if project_id in seen_projects:
                errors.append(f"review-sources.json: duplicate project_id {project_id}")
            seen_repositories.add(repository.lower())
            seen_projects.add(project_id)
            if project_map.get(repository) != project_id:
                errors.append(f"review-sources.json: {repository} does not match its canonical project profile")
            if item.get("enabled") not in {True, False}:
                errors.append(f"review-sources.json: {repository} enabled flag must be boolean")
            if type(item.get("since_days")) is not int or not 1 <= item["since_days"] <= 90:
                errors.append(f"review-sources.json: {repository} since_days must be 1..90")
            if type(item.get("max_prs")) is not int or not 1 <= item["max_prs"] <= 100:
                errors.append(f"review-sources.json: {repository} max_prs must be 1..100")
        security = review.get("security_contract", {})
        source_access = str(security.get("source_access", ""))
        sink_access = str(security.get("sink_access", ""))
        if "read-only" not in source_access or "pull-requests:read" not in source_access or "issues:read" not in source_access:
            errors.append("review-sources.json: source App must remain read-only for pull requests and issues")
        if "Engineering-System" not in sink_access or "only" not in sink_access:
            errors.append("review-sources.json: sink write boundary must remain canonical and exclusive")
        if "untrusted" not in str(security.get("execution", "")):
            errors.append("review-sources.json: source comments must remain untrusted data")
        if "never approves" not in str(security.get("approval", "")):
            errors.append("review-sources.json: intake must not adjudicate or approve Signals")
        for secret_path in contains_secret_key(review):
            errors.append(f"review-sources.json: secret-bearing field is forbidden at {secret_path}")
    except ValueError as exc:
        errors.append(str(exc))

    try:
        governance = read_json(governance_path)
        if governance.get("schema_version") != 1 or governance.get("kind") != "repository_merge_policy":
            errors.append("repository-governance.json: invalid schema_version or kind")
        records = governance.get("repositories")
        if not isinstance(records, list) or not records:
            errors.append("repository-governance.json: repositories must be a non-empty array")
            records = []
        seen: set[str] = set()
        expected_repositories = {
            "waelhe/app-java-v3",
            "waelhe/marketplace-admin",
            "waelhe/mobile-marketplace",
            "waelhe/Engineering-System",
        }
        found_repositories: set[str] = set()
        allowed_rules = {
            "deletion", "non_fast_forward", "required_linear_history",
            "pull_request", "required_status_checks",
        }
        for index, item in enumerate(records):
            if not isinstance(item, dict):
                errors.append(f"repository-governance.json: repositories[{index}] must be an object")
                continue
            repository = item.get("repository")
            if not isinstance(repository, str):
                errors.append(f"repository-governance.json: repositories[{index}].repository is required")
                continue
            if repository in seen:
                errors.append(f"repository-governance.json: duplicate repository {repository}")
            seen.add(repository)
            found_repositories.add(repository)
            if item.get("default_branch") != "main":
                errors.append(f"repository-governance.json: {repository} must target main")
            if repository == "waelhe/mobile-marketplace" and item.get("visibility") != "private":
                errors.append("repository-governance.json: mobile-marketplace must remain private")
            observed = item.get("observed", {})
            if observed.get("rulesets_api") not in {"readable", "plan_limited", "not_captured"}:
                errors.append(f"repository-governance.json: {repository} has invalid rulesets_api state")
            if observed.get("rulesets_api") == "plan_limited" and not observed.get("limitation"):
                errors.append(f"repository-governance.json: {repository} plan limitation must be explicit")
            expected = item.get("expected", {})
            required = expected.get("required_rules", [])
            if not isinstance(required, list) or not set(required).issubset(allowed_rules):
                errors.append(f"repository-governance.json: {repository} has invalid required_rules")
            checks = expected.get("required_status_checks", [])
            if not isinstance(checks, list) or any(not isinstance(check, str) or not check for check in checks):
                errors.append(f"repository-governance.json: {repository} required checks must be non-empty strings")
            if len(checks) != len(set(checks)):
                errors.append(f"repository-governance.json: {repository} required checks must be unique")
            approvals = expected.get("required_approving_review_count")
            if type(approvals) is not int or approvals < 0:
                errors.append(f"repository-governance.json: {repository} approval count must be a non-negative integer")
            if type(expected.get("require_thread_resolution")) is not bool:
                errors.append(f"repository-governance.json: {repository} thread-resolution policy must be boolean")
            merge_methods = expected.get("required_merge_methods", [])
            if not isinstance(merge_methods, list) or not set(merge_methods).issubset({"merge", "squash", "rebase"}):
                errors.append(f"repository-governance.json: {repository} has invalid merge methods")
        if found_repositories != expected_repositories:
            errors.append(
                "repository-governance.json: registered repositories differ from the four canonical project repositories"
            )
        for secret_path in contains_secret_key(governance):
            errors.append(f"repository-governance.json: secret-bearing field is forbidden at {secret_path}")
    except ValueError as exc:
        errors.append(str(exc))

    return errors


def validate_registry(root: Path = ROOT) -> list[str]:
    errors: list[str] = validate_auxiliary_registries(root)
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
        "capabilities": ("capability_registry", "app-java-v3.capabilities.json"),
        "risks": ("critical_risk_registry", "app-java-v3.critical-risks.json"),
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

    # W3 candidate capabilities are derived from journeys; they are not approved domain ownership or current implementation claims.
    capabilities = loaded.get("capabilities", {})
    capability_records = capabilities.get("records", [])
    journey_by_id = {item.get("journey_id"): item for item in journeys}
    capability_journey_ids = [item.get("source_journey_id") for item in capability_records]
    if sorted(capability_journey_ids) != expected_ids:
        errors.append("capability candidates must map exactly once to each canonical journey J01..J35")
    if len(capability_journey_ids) != len(set(capability_journey_ids)):
        errors.append("capability candidate journey references are not unique")
    for item in capability_records:
        source_journey = journey_by_id.get(item.get("source_journey_id"))
        if source_journey is None:
            errors.append(f"{item.get('capability_id')}: unknown source journey")
            continue
        if item.get("title") != source_journey.get("title"):
            errors.append(f"{item.get('capability_id')}: title differs from the source journey")
        if item.get("documented_module_names") != source_journey.get("owning_modules_as_documented", []):
            errors.append(f"{item.get('capability_id')}: documented module names differ from the journey source")
        if item.get("source_journey_status_authority") != source_journey.get("status_authority"):
            errors.append(f"{item.get('capability_id')}: source authority differs from the journey")
        if item.get("acceptance_state") != "candidate_not_adjudicated":
            errors.append(f"{item.get('capability_id')}: candidate cannot be promoted without adjudication")
        if item.get("module_mapping_status") != "not_adjudicated":
            errors.append(f"{item.get('capability_id')}: module ownership cannot be inferred from the journey snapshot")
        verification = item.get("verification", {})
        if any(verification.get(surface) != "not_revalidated" for surface in ("backend", "android", "admin", "provider", "production")):
            errors.append(f"{item.get('capability_id')}: historical status must remain not_revalidated")
        if verification.get("tested_head_sha") is not None or verification.get("workflow_run_ids"):
            errors.append(f"{item.get('capability_id')}: no current verification evidence is recorded")
    capability_source = capabilities.get("source", {})
    artifact = capability_source.get("journey_registry_artifact", {})
    journey_path = root / "registry" / "peos" / "app-java-v3.journeys.json"
    try:
        journey_relative_path = journey_path.relative_to(root).as_posix()
        git_blob = subprocess.run(
            ["git", "rev-parse", f"HEAD:{journey_relative_path}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        actual_blob_sha = git_blob.stdout.strip()
        if artifact.get("blob_sha") != actual_blob_sha:
            errors.append("capability registry journey artifact blob SHA is stale")
        if capability_source.get("upstream_project", {}).get("commit_sha") != loaded.get("journeys", {}).get("source", {}).get("commit_sha"):
            errors.append("capability registry upstream project SHA disagrees with journey registry")
        capability_schema = read_json(root / "schemas" / "peos-capabilities.schema.json")
        Draft202012Validator.check_schema(capability_schema)
        cap_errors = list(Draft202012Validator(capability_schema, format_checker=FormatChecker()).iter_errors(capabilities))
        for item in cap_errors:
            errors.append(f"app-java-v3.capabilities.json: {'/'.join(map(str, item.absolute_path))}: {item.message}")
    except Exception as exc:
        errors.append(f"capability registry source/schema validation failed: {exc}")
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
        "OPS-RAILWAY-003", "OPS-GRAFANA-005", "OPS-GITHUB-003",
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
        "OPS-RAILWAY-003": "deployment_succeeded_last_aggregate_probe_degraded",
        "OPS-GRAFANA-005": "metrics_ingested_alert_delivery_unconfigured",
        "OPS-GITHUB-003": "repair_pr_deployed_open_unreviewed",
    }
    for record_id, expected_state in expected_states.items():
        if by_operation.get(record_id, {}).get("state") != expected_state:
            errors.append(f"{record_id}: state must remain explicitly {expected_state} until reverified")

    # W4 risk data references authoritative source/PR evidence; it is not a second EGM findings store.
    risk_registry = loaded.get("risks", {})
    risk_records = risk_registry.get("records", [])
    risk_ids = [item.get("risk_id") for item in risk_records]
    if len(risk_records) != 7:
        errors.append(f"W4 must carry exactly 7 audited critical-risk records, found {len(risk_records)}")
    if len(risk_ids) != len(set(risk_ids)):
        errors.append("W4 critical-risk IDs are not unique")
    if risk_registry.get("source", {}).get("commit_sha") != boundaries.get("source", {}).get("commit_sha"):
        errors.append("W4 critical-risk source SHA must match the pinned W2 backend source SHA")
    for item in risk_records:
        pr = item.get("pull_request", {})
        checks = item.get("checks", {})
        review = item.get("review", {})
        if pr.get("head_sha") != checks.get("head_sha"):
            errors.append(f"{item.get('risk_id')}: CI evidence is not bound to the exact PR head")
        if review.get("approval_on_current_head") is True and review.get("latest_sha") != pr.get("head_sha"):
            errors.append(f"{item.get('risk_id')}: claimed exact-head review SHA does not match the PR head")
        if item.get("status") == "closed_verified":
            closure = item.get("closure_evidence") or {}
            if not closure.get("main_contains_merge_commit") or closure.get("post_merge_conclusion") != "success":
                errors.append(f"{item.get('risk_id')}: closed risk lacks merged-main and successful post-merge evidence")
            if closure.get("verified_main_sha") != risk_registry.get("source", {}).get("commit_sha"):
                errors.append(f"{item.get('risk_id')}: closure evidence main SHA differs from the W4 source snapshot")
        elif item.get("closure_evidence") is not None:
            errors.append(f"{item.get('risk_id')}: non-closed risk cannot carry closure evidence")

    try:
        risk_schema = read_json(root / "schemas" / "peos-critical-risks.schema.json")
        Draft202012Validator.check_schema(risk_schema)
        risk_errors = list(Draft202012Validator(risk_schema, format_checker=FormatChecker()).iter_errors(risk_registry))
        for item in risk_errors:
            errors.append(f"app-java-v3.critical-risks.json: {'/'.join(map(str, item.absolute_path))}: {item.message}")
    except Exception as exc:
        errors.append(f"invalid W4 critical-risk schema: {exc}")

    # W5-W7 are separately dated current-evidence snapshots. Keep W0-W4 historical pins intact.
    current_schema_path = root / "schemas" / "peos-current-evidence.schema.json"
    current_schema: dict[str, Any] | None = None
    try:
        current_schema = read_json(current_schema_path)
        Draft202012Validator.check_schema(current_schema)
    except Exception as exc:
        errors.append(f"invalid PEOS current-evidence schema: {exc}")

    current_snapshots = [
        ("w3_pr_queue_snapshot", "app-java-v3.w3-pr-queue.json"),
        ("w5_backend_commerce_snapshot", "app-java-v3.w5-backend-commerce.json"),
        ("w6_client_delivery_snapshot", "clients.w6-current.json"),
        ("w7_operations_snapshot", "operations.w7-current.json"),
    ]
    current_payloads: dict[str, dict[str, Any]] = {}
    for expected_kind, filename in current_snapshots:
        try:
            payload = read_json(root / "registry" / "peos" / filename)
            if current_schema is not None:
                current_errors = list(
                    Draft202012Validator(
                        current_schema, format_checker=FormatChecker()
                    ).iter_errors(payload)
                )
                for item in current_errors:
                    errors.append(
                        f"{filename}: {'/'.join(map(str, item.absolute_path))}: {item.message}"
                    )
            if payload.get("kind") != expected_kind:
                errors.append(f"{filename}: expected kind {expected_kind}")
            ids = [record.get("id") for record in payload.get("records", [])]
            if len(ids) != len(set(ids)):
                errors.append(f"{filename}: current evidence record IDs are not unique")
            current_payloads[expected_kind] = payload
        except ValueError as exc:
            errors.append(str(exc))

    w3 = current_payloads.get("w3_pr_queue_snapshot", {})
    w3_source = next(
        (item for item in w3.get("sources", []) if item.get("repository") == "waelhe/app-java-v3"),
        {},
    )
    w3_record_list = w3.get("records", [])
    w3_numbers = [item.get("pr_number") for item in w3_record_list]
    w3_records = {item.get("pr_number"): item for item in w3_record_list}
    if w3_source.get("ref") != "main" or not SHA_RE.fullmatch(str(w3_source.get("commit_sha", ""))):
        errors.append("W3 source must pin a full SHA from app-java-v3/main")
    if w3.get("open_pr_count") != len(w3_record_list):
        errors.append("W3 open_pr_count must equal the number of captured open PR records")
    if len(w3_numbers) != len(set(w3_numbers)):
        errors.append("W3 pull-request numbers must be unique")
    if any(item.get("state") != "open" for item in w3_record_list):
        errors.append("W3 queue may contain only currently open pull requests")
    if any(item.get("allowed_to_merge") is True or item.get("merge_policy") == "authorized_to_merge" for item in w3_record_list):
        errors.append("W3 inventory cannot grant merge authorization")
    if w3_records.get(787, {}).get("merge_policy") != "single_full_commerce_candidate":
        errors.append("W3 PR #787 must remain the single full-commerce release candidate")
    if not SHA_RE.fullmatch(str(w3_records.get(787, {}).get("head_sha", ""))):
        errors.append("W3 PR #787 must carry its exact current head SHA")
    for number in range(806, 812):
        if w3_records.get(number, {}).get("merge_policy") != "tracking_only_do_not_merge":
            errors.append(f"W3 PR #{number} must remain a tracking-only, do-not-merge review shard")
    stacked = w3_records.get(837, {})
    stacked_proof = (w3.get("special_rules", {}).get("stacked_prs") or [{}])[0]
    stacked_relation = stacked.get("base_relation")
    stacked_ahead = stacked_proof.get("ahead_by")
    if (
        stacked_relation not in {"stacked_base_behind_candidate", "stacked_base_matches_candidate"}
        or stacked.get("base_branch") != w3_records.get(787, {}).get("head_branch")
        or stacked.get("base_sha") != stacked_proof.get("base_sha")
        or stacked_proof.get("candidate_pr") != 787
        or stacked_proof.get("candidate_head_sha") != w3_records.get(787, {}).get("head_sha")
        or stacked_proof.get("comparison_status") not in {"ahead", "identical"}
        or not isinstance(stacked_ahead, int)
        or stacked_ahead < 0
        or stacked_proof.get("behind_by") != 0
        or not isinstance(stacked_proof.get("compare_url"), str)
        or not stacked_proof.get("compare_url", "").endswith(
            f"/compare/{stacked.get('base_sha')}...{w3_records.get(787, {}).get('head_sha')}"
        )
        or (stacked_proof.get("comparison_status") == "ahead" and stacked_ahead <= 0)
        or (stacked_proof.get("comparison_status") == "identical" and stacked_ahead != 0)
        or (stacked_relation == "stacked_base_behind_candidate" and stacked_ahead <= 0)
        or (stacked_relation == "stacked_base_matches_candidate" and stacked_ahead != 0)
    ):
        errors.append("W3 PR #837 must retain an exact Compare API proof against the current #787 head")

    w5 = current_payloads.get("w5_backend_commerce_snapshot", {})
    w5_source = next(
        (item for item in w5.get("sources", []) if item.get("repository") == "waelhe/app-java-v3"),
        {},
    )
    w5_records = {item.get("pr_number"): item for item in w5.get("records", [])}
    if w5_source.get("ref") != "main" or w5_source.get("commit_sha") != "8ab2c667aef190b58d88cb116d8ce004bf948cf9":
        errors.append("W5 must remain pinned to the measured app-java-v3 main SHA")
    if w5.get("open_pr_count") != 25:
        errors.append("W5 open-PR count must reflect the 2026-11-21 GitHub capture")
    if w5_records.get(787, {}).get("state") != "open":
        errors.append("W5 must preserve PR #787 as the single open full-commerce candidate")
    if w5_records.get(787, {}).get("head_sha") != "aa05af4494615fa299abba78091970c5a3a25c56":
        errors.append("W5 PR #787 head SHA does not match the 2026-11-21 capture")
    if w5_records.get(842, {}).get("state") != "merged":
        errors.append("W5 must record PR #842 as merged, not as an open candidate")
    if w5_records.get(840, {}).get("checks") is None or not any(
        item.get("conclusion") == "failure" for item in w5_records.get(840, {}).get("checks", [])
    ):
        errors.append("W5 must retain the observed failed workflow evidence for PR #840")
    if w5_records.get(832, {}).get("state") != "open":
        errors.append("W5 A1 PR #832 must remain open pending the owner accounting decision")

    w6 = current_payloads.get("w6_client_delivery_snapshot", {})
    w6_records = {item.get("surface"): item for item in w6.get("records", [])}
    android = w6_records.get("android", {})
    admin = w6_records.get("admin", {})
    if android.get("repository") != "waelhe/mobile-marketplace" or android.get("main_sha") != "3e2357ac3f5ed00cfffc51b2909c60f9f214f1f4":
        errors.append("W6 Android record must be pinned to the measured mobile-marketplace main SHA")
    if not str(android.get("runtime", "")).startswith("Expo SDK") or "React Native" not in android.get("runtime", ""):
        errors.append("W6 must represent the measured mobile stack as Expo/React Native")
    if android.get("journey_state") != "not_revalidated":
        errors.append("W6 mobile journeys must remain not_revalidated without current E2E proof")
    if admin.get("repository") != "waelhe/marketplace-admin" or admin.get("main_sha") != "982ecf3667d2242cab941737cb6a0bceaee7ffcb":
        errors.append("W6 Admin record must be pinned to the measured marketplace-admin main SHA")
    if admin.get("journey_state") != "not_revalidated":
        errors.append("W6 Admin journeys must remain not_revalidated without current E2E proof")

    w7 = current_payloads.get("w7_operations_snapshot", {})
    w7_records = {item.get("surface"): item for item in w7.get("records", [])}
    production = w7_records.get("production_backend", {})
    grafana = w7_records.get("alerting_and_routing", {})
    if production.get("service_state") != "online" or production.get("replicas_running") != 1:
        errors.append("W7 must preserve the observed live Railway service and replica state")
    if production.get("latest_attempt", {}).get("state") != "failed":
        errors.append("W7 must not hide the latest failed Railway deployment attempt")
    if production.get("latest_attempt", {}).get("failure_stage") != "BUILD_IMAGE":
        errors.append("W7 must preserve the measured Railway BUILD_IMAGE failure stage")
    if production.get("staged_changes") != 0:
        errors.append("W7 must record the observed absence of staged Railway changes")
    if grafana.get("contact_points_returned") != 0 or grafana.get("notification_policy_receiver") != "empty":
        errors.append("W7 must retain the empty Grafana contact-point/receiver evidence")
    if grafana.get("alert_rules_read_result") != "null":
        errors.append("W7 must not silently convert the unresolved Grafana alert-rule response into a zero count")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate historical W0-W4 and current W5-W7 PEOS evidence snapshots.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate_registry(args.root)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("PEOS inventory validation: PASS")
    print("Validated W0-W4 historical inventories plus W5 backend/commerce, W6 client delivery and W7 operations snapshots.")
    print("Historical journey labels remain not-revalidated; Maven and Modulith graphs are distinct; W4 closure requires merged-main and exact-SHA proof; W5-W7 remain SHA/date-bound; no merge or deployment is authorized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
