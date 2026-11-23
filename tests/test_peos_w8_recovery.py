from __future__ import annotations

import json
from pathlib import Path

from tools.peos_w8_validate import validate_w8_recovery_gates

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    return {
        "schema_version": 1,
        "kind": "w8_recovery_gates",
        "snapshot_date": "2026-11-23",
        "incident": {
            "incident_id": "W8-NEON-QUOTA-2026-11-23",
            "source_repository": "waelhe/app-java-v3",
            "source_ref": "main",
            "source_commit_sha": "9b5e29afd0a5a344a8ac04a51a51da32fe134d10",
            "failed_deployment_id": "b76e73fd-5ad7-469d-8aa5-e68f7b09ab3f",
            "service_id": "43b1b64b-9087-45d4-88ca-358a40c5a583",
            "capture_date": "2026-11-23",
            "capture_document": "docs/peos/w8-production-postgresql-quota-incident-2026-11-23.md",
            "immediate_cause": "external_postgresql_quota_refusal",
        },
        "state": "blocked_external",
        "gates": [
            {
                "id": "W8-G1", "name": "External Neon quota and account-owner decision",
                "owner": "Neon project account owner", "state": "blocked_external",
                "owner_action_required": True, "depends_on": [],
                "required_evidence": ["neon_plan", "quota_category", "billing_usage_and_reset", "owner_decision"],
                "evidence": [], "assessment": "The account owner has not yet supplied quota evidence and a decision."
            },
            {
                "id": "W8-G2", "name": "PostgreSQL connection recovery",
                "owner": "Platform operator", "state": "blocked",
                "owner_action_required": False, "depends_on": ["W8-G1"],
                "required_evidence": ["postgres_connection_acceptance", "read_only_query"],
                "evidence": [], "assessment": "Waiting for owner adjudication and restored database connectivity."
            },
            {
                "id": "W8-G3", "name": "Successful Railway production redeployment",
                "owner": "Platform operator", "state": "blocked",
                "owner_action_required": False, "depends_on": ["W8-G2"],
                "required_evidence": ["railway_deployment_success", "deployed_commit_sha"],
                "evidence": [], "assessment": "Waiting for PostgreSQL connection recovery."
            },
            {
                "id": "W8-G4", "name": "Application migration and readiness verification",
                "owner": "Platform operator", "state": "blocked",
                "owner_action_required": False, "depends_on": ["W8-G3"],
                "required_evidence": ["flyway_validation", "readiness_http_200"],
                "evidence": [], "assessment": "Waiting for a successful Railway deployment."
            },
            {
                "id": "W8-G5", "name": "Production smoke and post-deployment verification",
                "owner": "Platform operator", "state": "blocked",
                "owner_action_required": False, "depends_on": ["W8-G4"],
                "required_evidence": ["production_smoke_report", "post_deploy_observation"],
                "evidence": [], "assessment": "Waiting for migration and readiness verification."
            }
        ],
        "prohibitions": [
            "do_not_point_DB_URL_at_new_empty_project", "do_not_run_manual_migrations",
            "do_not_rotate_database_credentials_as_quota_workaround", "do_not_replace_live_database"
        ],
        "safety_boundary": {
            "production_changes_performed": False, "database_replacement_authorized": False,
            "manual_migrations_authorized": False, "credential_rotation_authorized": False
        },
        "assessment": "The outage remains blocked by an external Neon quota condition."
    }


def write_snapshot(tmp_path, payload):
    schema_dir = tmp_path / "schemas"
    registry_dir = tmp_path / "registry" / "peos"
    schema_dir.mkdir(parents=True)
    registry_dir.mkdir(parents=True)
    (schema_dir / "peos-w8-recovery.schema.json").write_text(
        (ROOT / "schemas" / "peos-w8-recovery.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (registry_dir / "w8-recovery-gates.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def evidence(kind):
    return {
        "kind": kind,
        "reference": "https://example.invalid/record/1",
        "captured_at": "2026-11-23T12:00:00Z",
        "result": "Observed and independently retained."
    }


def test_current_w8_recovery_register_is_valid_and_remains_blocked_external():
    assert validate_w8_recovery_gates(ROOT) == []


def test_w8_registry_rejects_recovered_claim_while_gates_are_unverified(tmp_path):
    payload = snapshot()
    payload["state"] = "recovered"
    write_snapshot(tmp_path, payload)
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("expected blocked_external" in error for error in errors)


def test_w8_registry_rejects_verified_gate_without_all_required_evidence(tmp_path):
    payload = snapshot()
    payload["gates"][0]["state"] = "verified"
    payload["gates"][0]["owner_action_required"] = False
    payload["state"] = "open"
    write_snapshot(tmp_path, payload)
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("verified gate is missing evidence" in error for error in errors)


def test_w8_registry_rejects_progress_before_predecessor_is_verified(tmp_path):
    payload = snapshot()
    payload["gates"][1]["state"] = "verified"
    payload["gates"][1]["evidence"] = [
        evidence("postgres_connection_acceptance"), evidence("read_only_query")
    ]
    write_snapshot(tmp_path, payload)
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("cannot progress before dependency W8-G1" in error for error in errors)


def test_w8_registry_accepts_ordered_progress_only_after_all_gate_proofs(tmp_path):
    payload = snapshot()
    payload["gates"][0]["state"] = "verified"
    payload["gates"][0]["owner_action_required"] = False
    payload["gates"][0]["evidence"] = [
        successful_evidence("neon_plan"), successful_evidence("quota_category"),
        successful_evidence("billing_usage_and_reset"), successful_evidence("owner_decision")
    ]
    payload["gates"][1]["state"] = "in_progress"
    payload["gates"][1]["evidence"] = [successful_evidence("postgres_connection_acceptance")]
    payload["state"] = "open"
    write_snapshot(tmp_path, payload)
    assert validate_w8_recovery_gates(tmp_path) == []


def test_w8_registry_rejects_removed_data_safety_prohibition(tmp_path):
    payload = snapshot()
    payload["prohibitions"].remove("do_not_replace_live_database")
    write_snapshot(tmp_path, payload)
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("prohibitions must remain complete" in error for error in errors)


def test_w8_registry_rejects_secret_shaped_fields(tmp_path):
    payload = snapshot()
    payload["database_url"] = "must-not-be-stored"
    write_snapshot(tmp_path, payload)
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("secret-bearing fields" in error for error in errors)


def successful_evidence(kind):
    result_by_kind = {
        "neon_plan": "observed",
        "quota_category": "observed",
        "billing_usage_and_reset": "observed",
        "owner_decision": "approved",
        "postgres_connection_acceptance": "success",
        "read_only_query": "success",
        "railway_deployment_success": "success",
        "deployed_commit_sha": "sha_bound",
        "flyway_validation": "success",
        "readiness_http_200": "200",
        "production_smoke_report": "passed",
        "post_deploy_observation": "healthy",
    }
    item = evidence(kind)
    item["result"] = result_by_kind[kind]
    if kind == "deployed_commit_sha":
        item["source_sha"] = "a" * 40
    return item


def test_w8_registry_accepts_recovery_only_after_all_ordered_gates_are_verified(tmp_path):
    payload = snapshot()
    for gate in payload["gates"]:
        gate["state"] = "verified"
        gate["owner_action_required"] = False
        gate["evidence"] = [
            successful_evidence(kind) for kind in gate["required_evidence"]
        ]
    payload["state"] = "recovered"
    write_snapshot(tmp_path, payload)
    assert validate_w8_recovery_gates(tmp_path) == []


def test_w8_registry_rejects_failed_evidence_inside_a_verified_gate(tmp_path):
    payload = snapshot()
    gate_one = payload["gates"][0]
    gate_one["state"] = "verified"
    gate_one["owner_action_required"] = False
    gate_one["evidence"] = [
        successful_evidence("neon_plan"),
        successful_evidence("quota_category"),
        successful_evidence("billing_usage_and_reset"),
        successful_evidence("owner_decision"),
    ]
    gate_two = payload["gates"][1]
    gate_two["state"] = "verified"
    gate_two["evidence"] = [
        evidence("postgres_connection_acceptance"),
        successful_evidence("read_only_query"),
    ]
    gate_two["evidence"][0]["result"] = "failure"
    payload["state"] = "open"
    write_snapshot(tmp_path, payload)
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("postgres_connection_acceptance result" in error for error in errors)


def test_w8_registry_rejects_weakened_required_evidence_contract(tmp_path):
    payload = snapshot()
    payload["gates"][0]["required_evidence"].remove("owner_decision")
    write_snapshot(tmp_path, payload)
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("required evidence differs from the approved gate contract" in error for error in errors)


def test_w8_deployed_commit_evidence_must_include_a_full_sha(tmp_path):
    payload = snapshot()
    for gate in payload["gates"][:2]:
        gate["state"] = "verified"
        gate["owner_action_required"] = False
        gate["evidence"] = [
            successful_evidence(kind) for kind in gate["required_evidence"]
        ]
    gate_three = payload["gates"][2]
    gate_three["state"] = "verified"
    gate_three["evidence"] = [
        successful_evidence("railway_deployment_success"),
        evidence("deployed_commit_sha"),
    ]
    gate_three["evidence"][1]["result"] = "sha_bound"
    payload["state"] = "open"
    write_snapshot(tmp_path, payload)
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("deployed_commit_sha must carry a full source_sha" in error for error in errors)


def test_w8_registry_rejects_duplicate_evidence_kinds(tmp_path):
    payload = snapshot()
    gate = payload["gates"][0]
    gate["evidence"] = [
        evidence("neon_plan"),
        evidence("neon_plan"),
    ]
    write_snapshot(tmp_path, payload)
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("evidence kinds must be unique" in error for error in errors)


def test_w8_validator_reports_non_object_registry_root_without_crashing(tmp_path):
    write_snapshot(tmp_path, [])
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("root must be a JSON object" in error for error in errors)


def test_w8_validator_reports_malformed_incident_and_required_evidence_without_crashing(tmp_path):
    payload = snapshot()
    payload["incident"] = "malformed"
    payload["gates"][0]["required_evidence"] = [{"not": "a string"}]
    write_snapshot(tmp_path, payload)
    errors = validate_w8_recovery_gates(tmp_path)
    assert any("incident record must be an object" in error for error in errors)
    assert any("required_evidence must be a non-empty unique string list" in error for error in errors)
