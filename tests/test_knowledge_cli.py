from __future__ import annotations

import json
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
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


def test_signal_snapshot_identity_is_project_scoped(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    second_profile = json.loads(
        (root / "knowledge/projects/sample-project.json").read_text(encoding="utf-8")
    )
    second_profile["project_id"] = "another-project"
    (root / "knowledge/projects/another-project.json").write_text(
        json.dumps(second_profile), encoding="utf-8"
    )
    payload = {
        "project_id": "sample-project",
        "provider": "github",
        "repository": "owner/repo",
        "source_id": "review-comment-shared",
        "source_url": "https://github.com/owner/repo/pull/8",
        "title": "Same source",
        "body": "Same source body",
    }

    first, first_path = knowledge.receive_signal(payload)
    payload["project_id"] = "another-project"
    second, second_path = knowledge.receive_signal(payload)

    assert first == second == "created"
    assert first_path != second_path
    assert json.loads(first_path.read_text(encoding="utf-8"))["project_id"] == "sample-project"
    assert json.loads(second_path.read_text(encoding="utf-8"))["project_id"] == "another-project"
    assert knowledge.receive_signal(payload)[0] == "duplicate"


def test_title_only_signal_edit_is_idempotent_by_body_snapshot(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    payload = {
        "project_id": "sample-project",
        "provider": "github",
        "repository": "owner/repo",
        "source_id": "review-comment-title-only",
        "source_url": "https://github.com/owner/repo/pull/8",
        "title": "Original title",
        "body": "Unchanged source body",
    }

    created, path = knowledge.receive_signal(payload)
    payload["title"] = "Edited title"
    duplicate, same_path = knowledge.receive_signal(payload)

    assert created == "created"
    assert duplicate == "duplicate"
    assert same_path == path
    assert json.loads(path.read_text(encoding="utf-8"))["title"] == "Original title"
    assert len(list((root / "knowledge/inbox").glob("*.json"))) == 1


def test_concurrent_signal_intake_publishes_one_complete_immutable_snapshot(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    payload = {
        "project_id": "sample-project",
        "provider": "github",
        "repository": "owner/repo",
        "source_id": "review-comment-concurrent",
        "source_url": "https://github.com/owner/repo/pull/9",
        "title": "Concurrent intake",
        "body": "A complete source payload that must never be partially written.",
    }
    real_link = knowledge.os.link
    barrier = threading.Barrier(2)

    def synchronized_link(source, destination):
        barrier.wait(timeout=5)
        return real_link(source, destination)

    monkeypatch.setattr(knowledge.os, "link", synchronized_link)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: knowledge.receive_signal(payload), range(2)))

    assert sorted(outcome for outcome, _ in results) == ["created", "duplicate"]
    signal_files = list((root / "knowledge/inbox").glob("*.json"))
    assert len(signal_files) == 1
    stored = json.loads(signal_files[0].read_text(encoding="utf-8"))
    assert stored["summary"] == payload["body"]
    assert stored["payload_digest"] == __import__("hashlib").sha256(
        payload["body"].encode("utf-8")
    ).hexdigest()


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
            "comparison_status": "ahead",
            "ahead_by": 1,
            "behind_by": 0,
            "proof_url": "https://github.com/owner/repo/compare/" + tested_sha + "..." + ("c" * 40),
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "target_verification": {
                "workflow": {
                    "name": "target-regression",
                    "run_id": "67890",
                    "conclusion": "success",
                    "tested_sha": "c" * 40,
                    "url": "https://github.com/owner/repo/actions/runs/67890",
                }
            },
        },
    )
    verification["sources"].append({
        "kind": "ci_run",
        "uri": verification["target_inclusion"]["target_verification"]["workflow"]["url"],
        "run_id": "67890",
        "commit_sha": "c" * 40,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    })
    verification["sources"].append({
        "kind": "commit",
        "uri": verification["target_inclusion"]["proof_url"],
        "repository": "owner/repo",
        "commit_sha": "c" * 40,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    })
    (root / "knowledge/findings/finding-closure-test.json").write_text(json.dumps(finding), encoding="utf-8")
    action_path = root / "knowledge/actions/action-closure-test.json"
    action_path.write_text(json.dumps(action), encoding="utf-8")
    verification_path = root / "knowledge/verifications/verification-closure-test.json"
    verification_path.write_text(json.dumps(verification), encoding="utf-8")

    assert knowledge.validate_all() == []

    action["project_id"] = "unrelated-project"
    action_path.write_text(json.dumps(action), encoding="utf-8")
    errors = knowledge.validate_all()
    assert any("closed code-defect Finding requires" in item["error"] for item in errors)

    action["project_id"] = finding["project_id"]
    action_path.write_text(json.dumps(action), encoding="utf-8")
    verification["project_id"] = "unrelated-project"
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    errors = knowledge.validate_all()
    assert any("closed code-defect Finding requires" in item["error"] for item in errors)

    verification["project_id"] = finding["project_id"]
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    assert knowledge.validate_all() == []

    verification["target_inclusion"]["target_verification"]["workflow"]["tested_sha"] = tested_sha
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    errors = knowledge.validate_all()
    assert any("closed code-defect Finding requires" in item["error"] for item in errors)
    verification["target_inclusion"]["target_verification"]["workflow"]["tested_sha"] = "c" * 40
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    assert knowledge.validate_all() == []

    verification["target_inclusion"]["target_verification"]["workflow"]["conclusion"] = "failure"
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    errors = knowledge.validate_all()
    assert any("closed code-defect Finding requires" in item["error"] for item in errors)
    verification["target_inclusion"]["target_verification"]["workflow"]["conclusion"] = "success"
    verification_path.write_text(json.dumps(verification), encoding="utf-8")

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
    verification["target_inclusion"]["comparison_status"] = "diverged"
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    errors = knowledge.validate_all()
    assert any("closed code-defect Finding requires" in item["error"] for item in errors)

    verification["target_inclusion"]["comparison_status"] = "ahead"
    verification["target_inclusion"]["behind_by"] = 1
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    errors = knowledge.validate_all()
    assert any("closed code-defect Finding requires" in item["error"] for item in errors)

    verification["target_inclusion"]["behind_by"] = 0
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
        "checks": [{
            "name": "unit-tests",
            "status": "success",
            "run_id": "12345",
            "tested_sha": tested_sha,
            "url": "https://github.com/owner/repo/actions/runs/12345",
        }],
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

    receipt["checks"][0]["url"] = None
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any("url" in item["error"] or "successful check" in item["error"]
               for item in knowledge.validate_receipts())

    receipt["checks"][0]["url"] = "https://github.com:443/owner/repo/actions/runs/12345"
    receipt["checks"][0]["run_id"] = "99999"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any("no successful check" in item["error"]
               for item in knowledge.validate_receipts())

    receipt["checks"][0]["run_id"] = "12345"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert knowledge.validate_receipts() == []



def test_merged_receipt_binds_reviewed_head_tested_sha_and_target_run_source(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    head_sha = "a" * 40
    tested_sha = "b" * 40
    target_sha = "c" * 40
    target_run_id = "987654321"
    target_run_url = f"https://github.com/owner/repo/actions/runs/{target_run_id}"
    receipt = {
        "schema_version": 1,
        "task_id": "receipt-merged-proof",
        "project_id": "sample-project",
        "repository": "owner/repo",
        "tier": "T2",
        "status": "merged",
        "head_sha": head_sha,
        "tested_sha": tested_sha,
        "target_sha": target_sha,
        "started_at": "2026-11-20T00:00:00Z",
        "completed_at": "2026-11-20T01:00:00Z",
        "knowledge_pack": {"generated_at": "2026-11-20T00:00:00Z", "record_ids": []},
        "checks": [{
            "name": "candidate-ci",
            "status": "success",
            "run_id": "123456789",
            "tested_sha": tested_sha,
            "url": "https://github.com/owner/repo/actions/runs/123456789",
        }],
        "reviews": [{
            "role": "Goldfish",
            "status": "completed",
            "independence_proof": "Fresh isolated review context with source-read evidence.",
            "reviewed_sha": head_sha,
        }],
        "write_boundary": ["tools/"],
        "target_inclusion": {
            "target_branch": "main",
            "target_sha": target_sha,
            "tested_sha": tested_sha,
            "target_branch_proof": {
                "kind": "github_branch_ref",
                "branch": "main",
                "commit_sha": target_sha,
                "uri": "https://api.github.com/repos/owner/repo/branches/main",
                "captured_at": "2026-11-20T01:00:00Z",
            },
            "candidate_inclusion": {
                "head_sha": head_sha,
                "tested_sha": tested_sha,
                "head_sha_is_ancestor": True,
                "comparison_status": "ahead",
                "ahead_by": 2,
                "behind_by": 0,
                "proof_url": f"https://api.github.com/repos/owner/repo/compare/{head_sha}...{tested_sha}",
            },
            "tested_sha_is_ancestor": True,
            "comparison_status": "ahead",
            "ahead_by": 3,
            "behind_by": 0,
            "proof_url": f"https://api.github.com/repos/owner/repo/compare/{tested_sha}...{target_sha}",
            "target_verification": {
                "workflow": {
                    "name": "Target branch regression",
                    "run_id": target_run_id,
                    "conclusion": "success",
                    "tested_sha": target_sha,
                    "url": target_run_url,
                    "source": {
                        "kind": "ci_run",
                        "uri": target_run_url,
                        "run_id": target_run_id,
                        "commit_sha": target_sha,
                        "captured_at": "2026-11-20T01:00:00Z",
                    },
                },
            },
        },
    }
    directory = root / "knowledge/execution-receipts"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "merged.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    assert knowledge.validate_receipts() == []

    receipt["target_inclusion"]["target_branch_proof"]["branch"] = "release"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any("target branch proof" in item["error"] for item in knowledge.validate_receipts())
    receipt["target_inclusion"]["target_branch_proof"]["branch"] = "main"

    receipt["target_inclusion"]["candidate_inclusion"]["comparison_status"] = "identical"
    receipt["target_inclusion"]["candidate_inclusion"]["ahead_by"] = 0
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any("candidate inclusion proof" in item["error"] for item in knowledge.validate_receipts())
    receipt["target_inclusion"]["candidate_inclusion"]["comparison_status"] = "ahead"
    receipt["target_inclusion"]["candidate_inclusion"]["ahead_by"] = 2

    receipt["target_inclusion"]["comparison_status"] = "identical"
    receipt["target_inclusion"]["ahead_by"] = 0
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any("target inclusion proof" in item["error"] for item in knowledge.validate_receipts())
    receipt["target_inclusion"]["comparison_status"] = "ahead"
    receipt["target_inclusion"]["ahead_by"] = 3

    receipt["target_inclusion"]["target_branch_proof"]["uri"] = (
        "https://evil.example/repos/owner/repo/branches/main"
    )
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any("target branch proof" in item["error"] for item in knowledge.validate_receipts())
    receipt["target_inclusion"]["target_branch_proof"]["uri"] = (
        "https://api.github.com/repos/owner/repo/branches/main"
    )

    receipt["target_inclusion"]["candidate_inclusion"]["proof_url"] = (
        f"https://evil.example/repos/owner/repo/compare/{head_sha}...{tested_sha}"
    )
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any("candidate inclusion proof" in item["error"] for item in knowledge.validate_receipts())
    receipt["target_inclusion"]["candidate_inclusion"]["proof_url"] = (
        f"https://api.github.com/repos/owner/repo/compare/{head_sha}...{tested_sha}"
    )

    receipt["target_inclusion"]["candidate_inclusion"]["head_sha"] = "d" * 40
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any(
        "candidate inclusion proof must bind" in item["error"]
        for item in knowledge.validate_receipts()
    )

    receipt["target_inclusion"]["candidate_inclusion"]["head_sha"] = head_sha
    receipt["target_inclusion"]["target_verification"]["workflow"]["source"]["uri"] = (
        "https://github.com/owner/repo/actions/runs/111"
    )
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any(
        "matching ci_run source record" in item["error"]
        for item in knowledge.validate_receipts()
    )

    receipt["target_inclusion"]["target_verification"]["workflow"]["source"]["uri"] = target_run_url
    receipt["target_inclusion"]["target_verification"]["workflow"]["url"] = (
        "https://evil.example/owner/repo/actions/runs/" + target_run_id
    )
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any(
        "successful target-SHA workflow" in item["error"]
        for item in knowledge.validate_receipts()
    )


def test_queued_receipt_check_may_have_no_run_evidence_yet():
    receipt = {
        "schema_version": 1,
        "task_id": "receipt-queued-check",
        "project_id": "sample-project",
        "repository": "owner/repo",
        "tier": "T0",
        "status": "in_progress",
        "head_sha": "a" * 40,
        "started_at": "2026-11-17T00:00:00Z",
        "knowledge_pack": {"generated_at": "2026-11-17T00:00:00Z", "record_ids": []},
        "checks": [{
            "name": "build",
            "status": "queued",
            "run_id": None,
            "tested_sha": None,
            "url": None,
        }],
        "reviews": [],
        "write_boundary": [],
    }

    assert knowledge.schema_errors(
        receipt, knowledge.load_schema(knowledge.RECEIPT_SCHEMA)
    ) == []


def test_t2_receipt_requires_goldfish_review_for_exact_head_sha(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    head_sha = "e" * 40
    receipt = {
        "schema_version": 1,
        "task_id": "receipt-t2-review-sha",
        "project_id": "sample-project",
        "repository": "owner/repo",
        "tier": "T2",
        "status": "verified",
        "head_sha": head_sha,
        "tested_sha": head_sha,
        "started_at": "2026-11-17T00:00:00Z",
        "knowledge_pack": {"generated_at": "2026-11-17T00:00:00Z", "record_ids": []},
        "checks": [{
            "name": "validation",
            "status": "success",
            "run_id": "123456",
            "tested_sha": head_sha,
            "url": "https://github.com/owner/repo/actions/runs/123456",
        }],
        "reviews": [{
            "role": "Goldfish",
            "status": "completed",
            "independence_proof": "separate review context and reviewer identity",
            "reviewed_sha": "f" * 40,
        }],
        "write_boundary": ["tools/"],
    }
    directory = root / "knowledge/execution-receipts"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "t2.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    errors = knowledge.validate_receipts()
    assert any("reviewed_sha" in item["error"] or "for receipt head_sha" in item["error"]
               for item in errors)

    receipt["reviews"][0]["reviewed_sha"] = head_sha
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

def test_new_case_schema_does_not_require_legacy_excerpt_unless_migrated():
    schema = knowledge.load_schema(knowledge.RECORD_SCHEMA)
    case = _minimal_record(
        "case-new-current",
        "case",
        [],
        completeness="partial",
    )

    assert knowledge.schema_errors(case, schema) == []

    case["migration_batch"] = "historical-import-2026-11"
    errors = knowledge.schema_errors(case, schema)
    assert any("legacy_excerpt" in error for error in errors)

    case["legacy_excerpt"] = "Preserved source excerpt."
    assert knowledge.schema_errors(case, schema) == []




def test_merged_receipt_binds_tested_sha_to_target_and_requires_target_regression(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    tested_sha = "a" * 40
    target_sha = "b" * 40
    receipt = {
        "schema_version": 1,
        "task_id": "receipt-merged-1",
        "project_id": "sample-project",
        "repository": "owner/repo",
        "tier": "T1",
        "status": "merged",
        "head_sha": tested_sha,
        "tested_sha": tested_sha,
        "target_sha": target_sha,
            "target_branch_proof": {
                "kind": "github_branch_ref",
                "branch": "main",
                "commit_sha": target_sha,
                "uri": "https://api.github.com/repos/owner/repo/branches/main",
                "captured_at": "2026-11-14T00:15:00Z",
            },
        "started_at": "2026-11-14T00:00:00Z",
        "knowledge_pack": {"generated_at": "2026-11-14T00:00:00Z", "record_ids": []},
        "checks": [{
            "name": "candidate-tests",
            "status": "success",
            "run_id": "56789",
            "tested_sha": tested_sha,
            "url": "https://github.com/owner/repo/actions/runs/56789",
        }],
        "reviews": [],
        "write_boundary": ["src/"],
        "target_inclusion": {
            "target_branch": "main",
            "target_sha": target_sha,
            "tested_sha": tested_sha,
            "candidate_inclusion": {
                "head_sha": tested_sha,
                "tested_sha": tested_sha,
                "head_sha_is_ancestor": True,
                "comparison_status": "identical",
                "ahead_by": 0,
                "behind_by": 0,
                "proof_url": f"https://api.github.com/repos/owner/repo/compare/{tested_sha}...{tested_sha}",
            },
            "tested_sha_is_ancestor": True,
            "comparison_status": "ahead",
            "ahead_by": 1,
            "behind_by": 0,
            "proof_url": f"https://api.github.com/repos/owner/repo/compare/{tested_sha}...{target_sha}",
            "target_verification": {
                "workflow": {
                    "name": "target-regression",
                    "run_id": "90123",
                    "conclusion": "success",
                    "tested_sha": target_sha,
                    "url": "https://github.com/owner/repo/actions/runs/90123",
                    "source": {
                        "kind": "ci_run",
                        "uri": "https://github.com/owner/repo/actions/runs/90123",
                        "run_id": "90123",
                        "commit_sha": target_sha,
                        "captured_at": "2026-11-14T00:30:00Z",
                    },
                }
            },
        },
    }
    directory = root / "knowledge/execution-receipts"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "merged.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    assert knowledge.validate_receipts() == []

    receipt["target_inclusion"]["tested_sha"] = "c" * 40
    path.write_text(json.dumps(receipt), encoding="utf-8")
    errors = knowledge.validate_receipts()
    assert any("target inclusion proof must bind" in item["error"] for item in errors)

    receipt["target_inclusion"]["tested_sha"] = tested_sha
    receipt["target_inclusion"]["target_verification"]["workflow"]["tested_sha"] = tested_sha
    path.write_text(json.dumps(receipt), encoding="utf-8")
    errors = knowledge.validate_receipts()
    assert any("matching ci_run source record" in item["error"] for item in errors)


def test_malformed_receipt_nested_fields_are_reported_without_crashing(tmp_path, monkeypatch):
    root = isolate_store(tmp_path, monkeypatch)
    directory = root / "knowledge/execution-receipts"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "malformed.json").write_text(json.dumps({
        "schema_version": 1,
        "task_id": "malformed",
        "project_id": "sample-project",
        "repository": "owner/repo",
        "tier": "T2",
        "status": "merged",
        "head_sha": "a" * 40,
        "tested_sha": "b" * 40,
        "target_sha": "c" * 40,
        "started_at": "2026-11-20T00:00:00Z",
        "completed_at": "2026-11-20T01:00:00Z",
        "knowledge_pack": {"generated_at": "2026-11-20T00:00:00Z", "record_ids": []},
        "checks": [],
        "reviews": [],
        "write_boundary": [],
        "target_inclusion": {"target_verification": None},
    }), encoding="utf-8")
    errors = knowledge.validate_receipts()
    assert errors
    assert any("target_inclusion" in item["error"] or "required" in item["error"] for item in errors)
