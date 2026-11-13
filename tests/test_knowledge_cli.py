from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import tools.egm_knowledge as knowledge


REPO = Path(__file__).resolve().parents[1]


def isolate_store(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "repo"
    (root / "knowledge").mkdir(parents=True)
    schemas = root / "schemas"
    schemas.mkdir()
    shutil.copy(REPO / "schemas/knowledge-record.schema.json", schemas)
    shutil.copy(REPO / "schemas/project-profile.schema.json", schemas)
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
        "title": "Potential credential leak",
        "body": "Log contains ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 and must be reviewed."
    }
    outcome, path = knowledge.receive_signal(payload)
    assert outcome == "created"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert "[REDACTED_GITHUB_TOKEN]" in stored["summary"]
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
    assert all(item["path"].endswith(".jsonl#" + item["id"]) for item in index["records"])
