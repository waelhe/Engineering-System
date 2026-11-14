from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
import tools.egm_knowledge as knowledge


REPO = Path(__file__).resolve().parents[1]


def isolate_store(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "repo"
    (root / "knowledge").mkdir(parents=True)
    schemas = root / "schemas"
    schemas.mkdir()
    shutil.copy(REPO / "schemas/knowledge-record.schema.json", schemas)
    shutil.copy(REPO / "schemas/project-profile.schema.json", schemas)
    shutil.copy(REPO / "schemas/execution-receipt.schema.json", schemas)
    for folder in knowledge.RECORD_DIRS:
        (root / "knowledge" / folder).mkdir(parents=True, exist_ok=True)
    (root / "knowledge/projects").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(knowledge, "ROOT", root)
    monkeypatch.setattr(knowledge, "KNOWLEDGE", root / "knowledge")
    monkeypatch.setattr(knowledge, "SCHEMAS", schemas)
    monkeypatch.setattr(knowledge, "RECORD_SCHEMA", schemas / "knowledge-record.schema.json")
    monkeypatch.setattr(knowledge, "PROFILE_SCHEMA", schemas / "project-profile.schema.json")
    monkeypatch.setattr(knowledge, "RECEIPT_SCHEMA", schemas / "execution-receipt.schema.json")
    profile = {
        "schema_version": 1,
        "project_id": "sample-project",
        "name": "Sample Project",
        "repositories": [{"name": "owner/repo", "default_branch": "main"}],
        "technology": [],
        "module_map": [],
        "source_of_truth": ["README.md"]
    }
    (root / "knowledge/projects/sample-project.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )
    return root


def sample_case(case_id: str = "case-ledger-rounding") -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": 1,
        "id": case_id,
        "type": "case",
        "project_id": "sample-project",
        "title": "Ledger rounding invariant",
        "summary": "Rounding at the line boundary caused ledger drift.",
        "completeness": "complete",
        "legacy_excerpt": "Test fixture: rounding at the line boundary caused ledger drift.",
        "assessment": "verified",
        "lifecycle": "open",
        "approval": "approved",
        "created_at": timestamp,
        "updated_at": timestamp,
        "actor": "test",
        "tags": ["ledger", "money"],
        "scope": {"modules": ["marketplace-ledger"]},
        "trigger": "A fractional allocation crossed a rounding boundary.",
        "causal_chain": ["line rounding", "aggregation drift"],
        "root_cause": "Rounding policy was applied at inconsistent aggregation levels.",
        "violated_invariants": ["debits must equal credits"],
        "sources": [{
            "kind": "document",
            "uri": "https://example.test/case",
            "captured_at": timestamp
        }],
        "relations": []
    }


def test_repository_seed_profile_and_empty_index_are_valid():
    assert knowledge.validate_all() == []
    assert knowledge.write_index(check=True)


def test_validation_rejects_unresolved_relations(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    record = sample_case()
    record["relations"] = [{"type": "exhibits", "target_id": "pattern-does-not-exist"}]
    (root / "knowledge/cases/case-ledger-rounding.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    errors = knowledge.validate_all()
    assert any("unresolved relation target" in item["error"] for item in errors)


def test_signal_intake_is_idempotent_and_redacts_secrets(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    payload = {
        "project_id": "sample-project",
        "provider": "github",
        "repository": "owner/repo",
        "source_id": "review-comment-42",
        "source_url": "https://github.com/owner/repo/pull/7?token=unsafe#discussion_r42",
        "source_kind": "github_comment",
        "title": "Potential credential leak: Bearer abcdefghijklmnopqrstuvwxyz12345",
        "body": "Log contains ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 and must be reviewed."
    }
    outcome, path = knowledge.receive_signal(payload)
    assert outcome == "created"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert "[REDACTED_GITHUB_TOKEN]" in stored["summary"]
    assert "abcdefghijklmnopqrstuvwxyz12345" not in stored["title"]
    assert "Bearer [REDACTED]" in stored["title"]
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890" not in stored["summary"]
    assert "token=" not in stored["sources"][0]["uri"]
    duplicate, same_path = knowledge.receive_signal(payload)
    assert duplicate == "duplicate"
    assert same_path == path
    assert len(list((root / "knowledge/inbox").glob("*.json"))) == 1


def test_edited_signal_body_creates_a_new_immutable_snapshot(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    payload = {
        "project_id": "sample-project",
        "provider": "github",
        "source_id": "review-comment-77",
        "source_url": "https://github.com/owner/repo/pull/8",
        "title": "Review comment",
        "body": "Original observation"
    }
    first, first_path = knowledge.receive_signal(payload)
    payload["body"] = "Edited observation"
    second, second_path = knowledge.receive_signal(payload)
    assert first == "created" and second == "created"
    assert first_path != second_path
    assert len(list((root / "knowledge/inbox").glob("*.json"))) == 2
    records = [json.loads(path.read_text(encoding="utf-8")) for path in (root / "knowledge/inbox").glob("*.json")]
    assert len({record["payload_digest"] for record in records}) == 2


def test_signal_intake_rejects_unregistered_project_without_writing(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    payload = {
        "project_id": "not-registered",
        "provider": "github",
        "source_id": "review-comment-unknown-project",
        "source_url": "https://github.com/owner/repo/pull/8",
        "title": "Unregistered project",
        "body": "An external signal for a project that is not registered.",
    }

    with pytest.raises(knowledge.KnowledgeError, match="unregistered project_id"):
        knowledge.receive_signal(payload)

    assert list((root / "knowledge/inbox").glob("*.json")) == []


@pytest.mark.parametrize("suffix", [".json", ".jsonl"])
def test_record_loader_rejects_symbolic_links_before_reading(tmp_path, monkeypatch, suffix):
    root = isolate_store(tmp_path, monkeypatch)
    external = tmp_path / f"external{suffix}"
    external.write_text("{}" if suffix == ".json" else "{}\n", encoding="utf-8")
    link = root / "knowledge" / "cases" / f"linked{suffix}"
    link.symlink_to(external)

    with pytest.raises(knowledge.KnowledgeError, match="symbolic links are not allowed"):
        knowledge.iter_records()


def _minimal_record(record_id, record_type, relations, lifecycle="investigating", **extra):
    timestamp = datetime.now(timezone.utc).isoformat()
    record = {
        "schema_version": 1,
        "id": record_id,
        "type": record_type,
        "project_id": "sample-project",
        "title": f"Test {record_type}",
        "summary": "Test record for verification closure semantics.",
        "assessment": "verified" if record_type == "verification" else "observed",
        "lifecycle": lifecycle,
        "approval": "not_required",
        "created_at": timestamp,
        "updated_at": timestamp,
        "actor": "test",
        "tags": [],
        "scope": {},
        "sources": [{
            "kind": "document",
            "uri": "https://example.test/source",
            "captured_at": timestamp,
        }],
        "relations": relations,
    }
    record.update(extra)
    return record


def test_closed_finding_requires_successful_verification_through_resolved_action(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    tested_sha = "a" * 40
    finding = _minimal_record(
        "finding-closure-test",
        "finding",
        [{"type": "resolved_by", "target_id": "action-closure-test"}],
        lifecycle="closed",
        closure_mode="code_defect",
        completeness="complete",
        claim="A regression defect has been repaired.",
        impact="The affected behavior no longer fails.",
    )
    action = _minimal_record(
        "action-closure-test",
        "action",
        [{"type": "proven_by", "target_id": "verification-closure-test"}],
    )
    verification = _minimal_record(
        "verification-closure-test",
        "verification",
        [],
        tested_sha=tested_sha,
        workflow={
            "name": "validation",
            "run_id": "12345",
            "conclusion": "success",
            "tested_sha": tested_sha,
            "url": "https://github.com/owner/repo/actions/runs/12345",
        },
        target_inclusion={
            "target_branch": "main",
            "target_sha": "c" * 40,
            "tested_sha": tested_sha,
            "included": True,
            "proof_url": "https://github.com/owner/repo/compare/" + tested_sha + "..." + ("c" * 40),
            "verified_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    verification["sources"].append({
        "kind": "commit",
        "uri": verification["target_inclusion"]["proof_url"],
        "repository": "owner/repo",
        "commit_sha": "c" * 40,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    })
    (root / "knowledge/findings/finding-closure-test.json").write_text(json.dumps(finding), encoding="utf-8")
    (root / "knowledge/actions/action-closure-test.json").write_text(json.dumps(action), encoding="utf-8")
    verification_path = root / "knowledge/verifications/verification-closure-test.json"
    verification_path.write_text(json.dumps(verification), encoding="utf-8")

    assert not any("closed Finding requires" in item["error"] for item in knowledge.validate_all())

    verification["workflow"]["conclusion"] = "failure"
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    errors = knowledge.validate_all()
    assert any("closed code-defect Finding requires a resolved Action linked to successful Verification" in item["error"] for item in errors)

    verification["workflow"]["conclusion"] = "success"
    verification["target_inclusion"]["included"] = False
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    errors = knowledge.validate_all()
    assert any("closed code-defect Finding requires a resolved Action linked to successful Verification" in item["error"] for item in errors)

    verification["target_inclusion"]["included"] = True
    verification["sources"] = [
        source for source in verification["sources"]
        if source.get("kind") != "commit"
    ]
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    errors = knowledge.validate_all()
    assert any("closed code-defect Finding requires a resolved Action linked to successful Verification" in item["error"] for item in errors)


def test_general_verification_record_does_not_require_target_inclusion(tmp_path, monkeypatch):
    isolate_store(tmp_path, monkeypatch)
    tested_sha = "d" * 40
    verification = _minimal_record(
        "verification-general-test",
        "verification",
        [],
        tested_sha=tested_sha,
        workflow={
            "name": "control-check",
            "run_id": "67890",
            "conclusion": "success",
            "tested_sha": tested_sha,
            "url": "https://github.com/owner/repo/actions/runs/67890",
        },
    )

    errors = knowledge.schema_errors(verification, knowledge.load_schema(knowledge.RECORD_SCHEMA))

    assert errors == []


def test_closed_finding_accepts_a_complete_alternate_proof_contract(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    timestamp = datetime.now(timezone.utc).isoformat()
    finding = _minimal_record(
        "finding-alternate-closure",
        "finding",
        [{"type": "resolved_by", "target_id": "action-alternate-closure"}],
        lifecycle="closed",
        closure_mode="alternate_proof",
        completeness="complete",
        claim="An organizational control gap has been addressed.",
        impact="The required operating process is now active.",
        alternate_closure_proof={
            "owner": "accountable-owner",
            "decision_or_control_id": "control-alternate-closure",
            "evidence_ids": ["evidence-alternate-closure"],
            "test_limitation": "The control is organizational and cannot be represented by a deterministic code test.",
            "residual_risk": True,
            "reassessment_at": timestamp,
        },
    )
    action = _minimal_record(
        "action-alternate-closure",
        "action",
        [],
        owner="accountable-owner",
        measurable_acceptance=["The approved process is operating and sampled evidence is retained."],
    )
    control = _minimal_record(
        "control-alternate-closure",
        "control",
        [],
        approval="approved",
        approver="authorized-reviewer",
        owner="accountable-owner",
    )
    evidence = _minimal_record(
        "evidence-alternate-closure",
        "evidence",
        [],
        sources=[{
            "kind": "document",
            "uri": "https://example.test/operating-evidence",
            "captured_at": timestamp,
        }],
    )
    (root / "knowledge/findings/finding-alternate-closure.json").write_text(json.dumps(finding), encoding="utf-8")
    (root / "knowledge/actions/action-alternate-closure.json").write_text(json.dumps(action), encoding="utf-8")
    (root / "knowledge/controls/control-alternate-closure.json").write_text(json.dumps(control), encoding="utf-8")
    (root / "knowledge/evidence/evidence-alternate-closure.json").write_text(json.dumps(evidence), encoding="utf-8")

    errors = knowledge.validate_all()

    assert not any("closed alternate-proof Finding" in item["error"] for item in errors)


def test_alternate_closure_with_residual_risk_requires_reassessment_date(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    timestamp = datetime.now(timezone.utc).isoformat()
    finding = _minimal_record(
        "finding-alternate-date",
        "finding",
        [],
        lifecycle="closed",
        closure_mode="alternate_proof",
        completeness="complete",
        claim="A policy gap has been addressed.",
        impact="The operating policy is now active.",
        alternate_closure_proof={
            "owner": "accountable-owner",
            "decision_or_control_id": "control-alternate-date",
            "evidence_ids": ["evidence-alternate-date"],
            "test_limitation": "This is an organizational control.",
            "residual_risk": True,
        },
    )
    errors = knowledge.schema_errors(finding, knowledge.load_schema(knowledge.RECORD_SCHEMA))
    assert any("reassessment_at" in item for item in errors)


def test_verified_receipt_requires_tested_sha_to_equal_head_sha(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    tested_sha = "b" * 40
    receipt = {
        "schema_version": 1,
        "task_id": "receipt-task-1",
        "project_id": "sample-project",
        "repository": "owner/repo",
        "tier": "T1",
        "status": "verified",
        "head_sha": "a" * 40,
        "tested_sha": tested_sha,
        "started_at": "2026-11-14T00:00:00Z",
        "knowledge_pack": {"generated_at": "2026-11-14T00:00:00Z", "record_ids": []},
        "checks": [{"name": "unit-tests", "status": "success", "tested_sha": tested_sha}],
        "reviews": [],
        "write_boundary": ["src/"],
    }
    directory = root / "knowledge/execution-receipts"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    errors = knowledge.validate_receipts()
    assert any("verified receipt tested_sha must equal head_sha" in item["error"] for item in errors)

    receipt["tested_sha"] = receipt["head_sha"]
    receipt["checks"][0]["tested_sha"] = receipt["head_sha"]
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert knowledge.validate_receipts() == []



def test_retrieval_ranks_exact_tags_and_scope(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    case = sample_case()
    (root / "knowledge/cases/case-ledger-rounding.json").write_text(
        json.dumps(case), encoding="utf-8"
    )
    knowledge.write_index()
    results = knowledge.retrieve("ledger allocation", "sample-project")
    assert results
    assert results[0]["id"] == "case-ledger-rounding"
    assert "ledger" in results[0]["matched_terms"]


def test_jsonl_migration_batches_are_loaded_as_individual_records(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    batch = root / "knowledge/cases/migration.jsonl"
    first = sample_case("case-migration-one")
    second = sample_case("case-migration-two")
    batch.write_text(
        json.dumps(first) + "\n" + json.dumps(second) + "\n",
        encoding="utf-8"
    )
    loaded = knowledge.iter_records()
    assert [record["id"] for _, record in loaded] == ["case-migration-one", "case-migration-two"]
    knowledge.write_index()
    index = json.loads((root / "knowledge/index.json").read_text(encoding="utf-8"))
    assert index["record_count"] == 2
    assert {item["path"] for item in index["records"]} == {"knowledge/cases/migration.jsonl"}
    assert {item["id"] for item in index["records"]} == {"case-migration-one", "case-migration-two"}
