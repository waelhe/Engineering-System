import json
from pathlib import Path

from tools.validate_migration import validate_migration


def write_fixture(root: Path):
    (root / "migration").mkdir(parents=True)
    (root / "knowledge" / "cases").mkdir(parents=True)
    (root / "knowledge" / "projects").mkdir(parents=True)
    revision = "a" * 40
    manifest = {
        "schema_version": 1,
        "migration_batch": "batch-1",
        "expected_total_records": 1,
        "source": {"candidate_sha": revision, "candidate_is_merged": False},
        "families": [{
            "family": "cases",
            "type": "case",
            "path": "knowledge/cases/cases.jsonl",
            "project_id": "sample",
            "expected_count": 1,
            "expected_legacy_ids": ["E-01"],
            "source_artifact": {"revision": revision, "git_blob_sha": "b" * 40},
        }],
        "project_profiles": [{
            "path": "knowledge/projects/sample.json",
            "project_id": "sample",
            "source_baseline_sha": "c" * 40,
            "source_candidate_sha": revision,
            "candidate_pr": 834,
        }],
        "evidence_count_breakdown": {
            "source_snapshots": 8,
            "repair_reconciliations": 5,
            "additional_records": ["PR-834-INDEPENDENT-REVIEW-ATTEMPT", "LEGACY-COUNTING-POLICY"],
        },
    }
    record = {
        "id": "case-e-01", "type": "case", "project_id": "sample",
        "legacy_id": "E-01", "legacy_source_revision": revision,
        "migration_batch": "batch-1",
    }
    profile = {
        "project_id": "sample", "baseline_sha": "c" * 40,
        "candidate_sha": revision, "candidate_pr": 834,
        "profile_status": "candidate_data_imported",
    }
    (root / "migration" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "knowledge" / "cases" / "cases.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    (root / "knowledge" / "projects" / "sample.json").write_text(json.dumps(profile), encoding="utf-8")
    return root / "migration" / "manifest.json"


def test_migration_validator_accepts_exact_source_inventory(tmp_path: Path):
    manifest = write_fixture(tmp_path)
    assert validate_migration(tmp_path, manifest) == []


def test_migration_validator_detects_missing_extra_ids_and_wrong_provenance(tmp_path: Path):
    manifest = write_fixture(tmp_path)
    path = tmp_path / "knowledge" / "cases" / "cases.jsonl"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["legacy_id"] = "E-02"
    record["legacy_source_revision"] = "d" * 40
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    errors = validate_migration(tmp_path, manifest)

    assert any("missing legacy IDs: E-01" in item for item in errors)
    assert any("unexpected legacy IDs: E-02" in item for item in errors)
    assert any("legacy_source_revision does not match pinned source" in item for item in errors)
