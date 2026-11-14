import json
from pathlib import Path

from tools.validate_migration import validate_migration

FAMILIES = (
    ("cases", "case", "knowledge/cases/cases.jsonl"),
    ("findings", "finding", "knowledge/findings/findings.jsonl"),
    ("evidence", "evidence", "knowledge/evidence/evidence.jsonl"),
    ("patterns", "pattern", "knowledge/patterns/patterns.jsonl"),
    ("rules", "rule", "knowledge/rules/rules.jsonl"),
    ("controls", "control", "knowledge/controls/controls.jsonl"),
)


def write_fixture(root: Path):
    (root / "migration").mkdir(parents=True)
    revision = "a" * 40
    families = []
    for name, record_type, relative in FAMILIES:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        ids = ["E-01"] if name == "cases" else []
        families.append({
            "family": name,
            "type": record_type,
            "path": relative,
            "project_id": "sample",
            "expected_count": len(ids),
            "expected_legacy_ids": ids,
            "source_artifact": {"revision": revision, "git_blob_sha": "b" * 40},
        })
        records = []
        if name == "cases":
            records.append({
                "id": "case-e-01", "type": "case", "project_id": "sample",
                "legacy_id": "E-01", "legacy_source_revision": revision,
                "migration_batch": "batch-1",
            })
        destination.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )

    manifest = {
        "schema_version": 1,
        "migration_batch": "batch-1",
        "expected_total_records": 1,
        "source": {"candidate_sha": revision, "candidate_is_merged": False},
        "families": families,
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
    (root / "knowledge" / "projects").mkdir(parents=True)
    profile = {
        "project_id": "sample", "baseline_sha": "c" * 40,
        "candidate_sha": revision, "candidate_pr": 834,
        "profile_status": "candidate_data_imported",
    }
    (root / "migration" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "knowledge" / "projects" / "sample.json").write_text(json.dumps(profile), encoding="utf-8")
    return root / "migration" / "manifest.json"


def test_migration_validator_accepts_complete_source_family_inventory(tmp_path: Path):
    manifest = write_fixture(tmp_path)
    assert validate_migration(tmp_path, manifest) == []



def test_migration_validator_rejects_missing_project_profile_inventory(tmp_path: Path):
    manifest = write_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["project_profiles"] = []
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_migration(tmp_path, manifest)

    assert any("project_profiles must be a non-empty inventory" in item for item in errors)
    assert any("project profile inventory is missing: sample" in item for item in errors)


def test_migration_validator_rejects_incomplete_project_profile_entry(tmp_path: Path):
    manifest = write_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    del payload["project_profiles"][0]["source_baseline_sha"]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_migration(tmp_path, manifest)

    assert any("source_baseline_sha must be a full lowercase commit SHA" in item for item in errors)


def test_migration_validator_rejects_symlinked_profile_file(tmp_path: Path):
    manifest = write_fixture(tmp_path)
    profile_path = tmp_path / "knowledge" / "projects" / "sample.json"
    external = tmp_path / "external-profile.json"
    external.write_text(profile_path.read_text(encoding="utf-8"), encoding="utf-8")
    profile_path.unlink()
    profile_path.symlink_to(external)

    errors = validate_migration(tmp_path, manifest)

    assert any("symbolic links are not allowed" in item for item in errors)


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



def test_migration_validator_rejects_candidate_sha_not_matching_source_revision(tmp_path: Path):
    manifest = write_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    alternate = "d" * 40
    payload["project_profiles"][0]["source_candidate_sha"] = alternate
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    profile_path = tmp_path / "knowledge" / "projects" / "sample.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["candidate_sha"] = alternate
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    errors = validate_migration(tmp_path, manifest)

    assert any("source_candidate_sha does not match pinned source revision" in item for item in errors)
