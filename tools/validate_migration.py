#!/usr/bin/env python3
"""Verify the app-java-v3 migration against its pinned source inventory."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "migration" / "app-java-v3-2026-11-13.manifest.json"


def _ensure_safe_file(path: Path, root: Path) -> None:
    root_path = root.absolute()
    candidate = path.absolute()
    try:
        relative = candidate.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(f"{path}: path escapes migration repository root") from exc
    current = root_path
    if current.is_symlink():
        raise ValueError(f"{current}: symbolic links are not allowed in migration inputs")
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{current}: symbolic links are not allowed in migration inputs")
    if not candidate.is_file():
        raise ValueError(f"{candidate}: migration input must be a regular file")


def _read_json(path: Path, root: Path = ROOT) -> Any:
    _ensure_safe_file(path, root)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: cannot read valid JSON: {exc}") from exc


def _read_jsonl(path: Path, root: Path = ROOT) -> list[dict[str, Any]]:
    _ensure_safe_file(path, root)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"{path}: cannot read JSONL: {exc}") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: record must be an object")
        records.append(value)
    return records


def validate_migration(root: Path = ROOT, manifest_path: Path = MANIFEST) -> list[str]:
    errors: list[str] = []
    try:
        manifest = _read_json(manifest_path, root)
    except ValueError as exc:
        return [str(exc)]
    if not isinstance(manifest, dict):
        return ["migration manifest root must be a JSON object"]

    source = manifest.get("source", {})
    source_revision = source.get("candidate_sha") if isinstance(source, dict) else None
    batch = manifest.get("migration_batch")
    families = manifest.get("families", [])
    if manifest.get("schema_version") != 1:
        errors.append("unsupported manifest schema_version")
    if not isinstance(source_revision, str) or len(source_revision) != 40:
        errors.append("manifest source.candidate_sha must be a full commit SHA")
    if not isinstance(batch, str) or not batch:
        errors.append("manifest migration_batch is required")
    if not isinstance(source, dict) or source.get("candidate_is_merged") is not False:
        errors.append("manifest must preserve the source candidate as unmerged")
    if not isinstance(families, list) or not families:
        errors.append("manifest families must be a non-empty array")
        return errors

    total_expected = 0
    family_names: set[str] = set()
    for family in families:
        name = family.get("family", "<unnamed>")
        if name in family_names:
            errors.append(f"duplicate manifest family: {name}")
        family_names.add(name)
        relative = family.get("path")
        expected_ids = family.get("expected_legacy_ids")
        expected_count = family.get("expected_count")
        artifact = family.get("source_artifact", {})
        target = Path(relative) if isinstance(relative, str) else Path("..")
        if target.is_absolute() or ".." in target.parts:
            errors.append(f"{name}: target path must remain inside repository")
            continue
        if not isinstance(expected_ids, list) or not all(isinstance(x, str) for x in expected_ids):
            errors.append(f"{name}: expected_legacy_ids must be a string array")
            continue
        if len(set(expected_ids)) != len(expected_ids):
            errors.append(f"{name}: manifest contains duplicate expected legacy IDs")
        if expected_count != len(expected_ids):
            errors.append(f"{name}: expected_count does not match manifest ID inventory")
        total_expected += len(expected_ids)
        if not isinstance(artifact, dict) or artifact.get("revision") != source_revision:
            errors.append(f"{name}: source artifact revision does not match source candidate SHA")
        elif not isinstance(artifact.get("git_blob_sha"), str) or len(artifact.get("git_blob_sha")) != 40:
            errors.append(f"{name}: source artifact Git blob SHA is missing or malformed")

        try:
            records = _read_jsonl(root / target, root)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        ids: list[str] = []
        record_ids: list[str] = []
        for index, record in enumerate(records, start=1):
            legacy_id = record.get("legacy_id")
            record_id = record.get("id")
            if isinstance(legacy_id, str) and legacy_id:
                ids.append(legacy_id)
            else:
                errors.append(f"{name}:{index}: missing legacy_id")
            if isinstance(record_id, str) and record_id:
                record_ids.append(record_id)
            else:
                errors.append(f"{name}:{index}: missing id")
            if record.get("type") != family.get("type"):
                errors.append(f"{name}:{index}: expected type {family.get('type')!r}, got {record.get('type')!r}")
            if record.get("project_id") != family.get("project_id"):
                errors.append(f"{name}:{index}: project_id does not match manifest")
            if record.get("legacy_source_revision") != source_revision:
                errors.append(f"{name}:{index}: legacy_source_revision does not match pinned source")
            if record.get("migration_batch") != batch:
                errors.append(f"{name}:{index}: migration_batch does not match manifest")

        if len(records) != expected_count:
            errors.append(f"{name}: expected {expected_count} records, found {len(records)}")
        if len(set(record_ids)) != len(record_ids):
            errors.append(f"{name}: duplicate destination record IDs")
        if len(set(ids)) != len(ids):
            errors.append(f"{name}: duplicate legacy IDs in destination")
        missing = sorted(set(expected_ids) - set(ids))
        extra = sorted(set(ids) - set(expected_ids))
        if missing:
            errors.append(f"{name}: missing legacy IDs: {', '.join(missing)}")
        if extra:
            errors.append(f"{name}: unexpected legacy IDs: {', '.join(extra)}")

    if total_expected != manifest.get("expected_total_records"):
        errors.append("expected_total_records does not equal sum of family inventories")
    if family_names != {"cases", "findings", "evidence", "patterns", "rules", "controls"}:
        errors.append("manifest family set is incomplete or contains unexpected families")

    expected_project_ids = {
        family.get("project_id")
        for family in families
        if isinstance(family, dict) and isinstance(family.get("project_id"), str) and family.get("project_id")
    }
    project_profiles = manifest.get("project_profiles")
    if not isinstance(project_profiles, list) or not project_profiles:
        errors.append("project_profiles must be a non-empty inventory; migration provenance cannot PASS without it")
        project_profiles = []

    seen_project_ids: set[str] = set()
    for index, profile in enumerate(project_profiles, start=1):
        if not isinstance(profile, dict):
            errors.append(f"project_profiles[{index}] must be an object")
            continue
        project_id = profile.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            errors.append(f"project_profiles[{index}] requires a non-empty project_id")
            continue
        if project_id in seen_project_ids:
            errors.append(f"duplicate project profile inventory entry: {project_id}")
        seen_project_ids.add(project_id)
        if project_id not in expected_project_ids:
            errors.append(f"project profile {project_id} is not represented by a migrated family")

        relative_text = profile.get("path")
        if not isinstance(relative_text, str) or not relative_text:
            errors.append(f"project profile {project_id} requires a repository-relative path")
            continue
        relative = Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"{project_id}: project profile path must remain inside repository")
            continue

        baseline = profile.get("source_baseline_sha")
        candidate = profile.get("source_candidate_sha")
        candidate_pr = profile.get("candidate_pr")
        if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline):
            errors.append(f"{project_id}: source_baseline_sha must be a full lowercase commit SHA")
        if not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-f]{40}", candidate):
            errors.append(f"{project_id}: source_candidate_sha must be a full lowercase commit SHA")
        elif candidate != source_revision:
            errors.append(f"{project_id}: source_candidate_sha does not match pinned source revision")
        if not isinstance(candidate_pr, int) or isinstance(candidate_pr, bool) or candidate_pr < 1:
            errors.append(f"{project_id}: candidate_pr must be a positive integer")

        try:
            value = _read_json(root / relative, root)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        expected_fields = {
            "project_id": project_id,
            "baseline_sha": baseline,
            "candidate_sha": candidate,
            "candidate_pr": candidate_pr,
        }
        for field, expected in expected_fields.items():
            if value.get(field) != expected:
                errors.append(f"{relative}: {field} does not match manifest")
        if value.get("profile_status") != "candidate_data_imported":
            errors.append(f"{relative}: profile must remain candidate_data_imported until cutover")

    missing_project_ids = expected_project_ids - seen_project_ids
    if missing_project_ids:
        errors.append("project profile inventory is missing: " + ", ".join(sorted(missing_project_ids)))

    breakdown = manifest.get("evidence_count_breakdown", {})
    if breakdown.get("source_snapshots") != 8:
        errors.append("evidence manifest must account for eight source snapshots")
    if breakdown.get("repair_reconciliations") != 5:
        errors.append("evidence manifest must account for five repair reconciliations")
    if breakdown.get("additional_records") != ["PR-834-INDEPENDENT-REVIEW-ATTEMPT", "LEGACY-COUNTING-POLICY"]:
        errors.append("evidence manifest additional-record inventory is incorrect")
    return errors


def main() -> int:
    errors = validate_migration()
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    manifest = _read_json(MANIFEST)
    print(json.dumps({
        "status": "PASS",
        "source_revision": manifest["source"]["candidate_sha"],
        "migration_batch": manifest["migration_batch"],
        "record_count": manifest["expected_total_records"],
        "families": {item["family"]: item["expected_count"] for item in manifest["families"]},
        "cutover": "not_authorized",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
