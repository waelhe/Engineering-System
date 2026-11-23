"""Fail-closed validation for the W8 production recovery gate register."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_GATES = [
    ("W8-G1", []),
    ("W8-G2", ["W8-G1"]),
    ("W8-G3", ["W8-G2"]),
    ("W8-G4", ["W8-G3"]),
    ("W8-G5", ["W8-G4"]),
]
EXPECTED_PROHIBITIONS = [
    "do_not_point_DB_URL_at_new_empty_project",
    "do_not_run_manual_migrations",
    "do_not_rotate_database_credentials_as_quota_workaround",
    "do_not_replace_live_database",
]
EXPECTED_SAFETY_BOUNDARY = {
    "production_changes_performed": False,
    "database_replacement_authorized": False,
    "manual_migrations_authorized": False,
    "credential_rotation_authorized": False,
}
SECRET_KEYS = {
    "token", "access_token", "refresh_token", "private_key", "secret",
    "client_secret", "password", "connection_string", "database_url", "db_url",
}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc


def _secret_key_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in SECRET_KEYS:
                found.append(child)
            found.extend(_secret_key_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_secret_key_paths(item, f"{path}[{index}]"))
    return found


def validate_w8_recovery_gates(root: Path = ROOT) -> list[str]:
    """Validate W8 recovery claims against exact gates and explicit evidence."""
    errors: list[str] = []
    schema_path = root / "schemas" / "peos-w8-recovery.schema.json"
    registry_path = root / "registry" / "peos" / "w8-recovery-gates.json"

    try:
        schema = _read_json(schema_path)
        Draft202012Validator.check_schema(schema)
        payload = _read_json(registry_path)
    except Exception as exc:
        return [f"W8 recovery registry/schema cannot be loaded: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for item in validator.iter_errors(payload):
        location = "/".join(map(str, item.absolute_path))
        errors.append(f"w8-recovery-gates.json: {location}: {item.message}")

    if payload.get("kind") != "w8_recovery_gates":
        errors.append("W8 recovery registry must use kind=w8_recovery_gates")

    incident = payload.get("incident", {})
    fixed_incident = {
        "incident_id": "W8-NEON-QUOTA-2026-11-23",
        "source_repository": "waelhe/app-java-v3",
        "source_ref": "main",
        "source_commit_sha": "9b5e29afd0a5a344a8ac04a51a51da32fe134d10",
        "failed_deployment_id": "b76e73fd-5ad7-469d-8aa5-e68f7b09ab3f",
        "service_id": "43b1b64b-9087-45d4-88ca-358a40c5a583",
        "capture_date": "2026-11-23",
        "capture_document": "docs/peos/w8-production-postgresql-quota-incident-2026-11-23.md",
        "immediate_cause": "external_postgresql_quota_refusal",
    }
    for key, expected in fixed_incident.items():
        if incident.get(key) != expected:
            errors.append(f"W8 incident source pin mismatch: {key}")

    gates = payload.get("gates", [])
    if not isinstance(gates, list):
        return errors + ["W8 gates must be an array"]

    observed_ids = [item.get("id") for item in gates if isinstance(item, dict)]
    expected_ids = [item[0] for item in EXPECTED_GATES]
    if observed_ids != expected_ids:
        errors.append("W8 recovery gates must remain ordered W8-G1 through W8-G5")

    by_id = {
        item.get("id"): item for item in gates
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for gate_id, dependencies in EXPECTED_GATES:
        gate = by_id.get(gate_id)
        if gate is None:
            continue
        if gate.get("depends_on") != dependencies:
            errors.append(f"{gate_id}: recovery dependency chain differs from the approved sequence")
        state = gate.get("state")
        evidence = gate.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
        evidence_kinds = [
            item.get("kind") for item in evidence
            if isinstance(item, dict) and isinstance(item.get("kind"), str)
        ]
        if len(evidence_kinds) != len(set(evidence_kinds)):
            errors.append(f"{gate_id}: evidence kinds must be unique")
        required = gate.get("required_evidence", [])
        if not isinstance(required, list) or not required or len(required) != len(set(required)):
            errors.append(f"{gate_id}: required_evidence must be a non-empty unique list")
        elif state == "verified":
            missing = sorted(set(required) - set(evidence_kinds))
            if missing:
                errors.append(f"{gate_id}: verified gate is missing evidence: {', '.join(missing)}")
        elif state == "in_progress" and not evidence:
            errors.append(f"{gate_id}: in_progress requires at least one captured evidence item")

        if state == "blocked_external" and gate.get("owner_action_required") is not True:
            errors.append(f"{gate_id}: blocked_external requires an explicit owner action")
        if state == "verified" and gate.get("owner_action_required") is True:
            errors.append(f"{gate_id}: verified gate cannot still require owner action")

        for dependency in dependencies:
            dependency_gate = by_id.get(dependency)
            if dependency_gate and state in {"in_progress", "verified"} and dependency_gate.get("state") != "verified":
                errors.append(f"{gate_id}: cannot progress before dependency {dependency} is verified")

    if payload.get("prohibitions") != EXPECTED_PROHIBITIONS:
        errors.append("W8 recovery prohibitions must remain complete and ordered")
    if payload.get("safety_boundary") != EXPECTED_SAFETY_BOUNDARY:
        errors.append("W8 recovery safety boundary must remain fail-closed")

    derived_state = (
        "recovered" if gates and all(
            isinstance(item, dict) and item.get("state") == "verified" for item in gates
        )
        else "blocked_external" if any(
            isinstance(item, dict) and item.get("state") == "blocked_external" for item in gates
        )
        else "open"
    )
    if payload.get("state") != derived_state:
        errors.append(f"W8 incident state must be derived from its gates: expected {derived_state}")

    for path in _secret_key_paths(payload):
        errors.append(f"W8 recovery registry forbids secret-bearing fields at {path}")

    return errors
