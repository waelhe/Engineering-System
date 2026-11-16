#!/usr/bin/env python3
"""Validate a trusted, data-only knowledge intake PR without executing its branch."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Iterable

from tools.knowledge_guard import validate_changes

ROOT = Path(__file__).resolve().parents[1]
HEAD_REF_PATTERN = re.compile(r"^automation/knowledge-intake-[0-9]+-[0-9]+$")
HEAD_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SIGNAL_PATH_PATTERN = re.compile(r"^knowledge/inbox/sig-[0-9a-f]{24}\.json$")
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class IntakeValidationError(RuntimeError):
    pass


def git(*args: str, check: bool = True, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if check and result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise IntakeValidationError(detail or f"git {' '.join(args)} failed")
    return result.stdout if binary else result.stdout.decode("utf-8", errors="replace")


def validate_ref_name(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("-")
        or ".." in value
        or "@{" in value
    ):
        raise IntakeValidationError(f"{label} is not a safe Git branch ref")
    result = subprocess.run(
        ["git", "check-ref-format", "--branch", value],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise IntakeValidationError(f"{label} is not a valid Git branch ref")
    return value


def validate_change_set(changes: Iterable[tuple[str, str]]) -> tuple[list[str], str]:
    signal_paths: list[str] = []
    index_changed = False
    for status, path in changes:
        if status == "A" and SIGNAL_PATH_PATTERN.fullmatch(path):
            signal_paths.append(path)
            continue
        if path == "knowledge/index.json" and status == "M" and not index_changed:
            index_changed = True
            continue
        raise IntakeValidationError(
            f"intake PR contains a prohibited change: {status} {path}"
        )
    if not signal_paths:
        raise IntakeValidationError("intake PR must add at least one immutable Signal JSON file")
    if not index_changed:
        raise IntakeValidationError("intake PR must update generated knowledge/index.json")
    if len(signal_paths) != len(set(signal_paths)):
        raise IntakeValidationError("intake PR contains duplicate Signal paths")
    return sorted(signal_paths), "knowledge/index.json"


def validate_signal_record(relative_path: str, content: bytes) -> None:
    """Check that an added inbox blob is a genuine untrusted Signal-shaped snapshot."""
    if not SIGNAL_PATH_PATTERN.fullmatch(relative_path):
        raise IntakeValidationError(f"invalid Signal path: {relative_path}")
    try:
        record = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntakeValidationError(f"Signal is not valid UTF-8 JSON: {relative_path}") from exc
    if not isinstance(record, dict) or record.get("type") != "signal":
        raise IntakeValidationError(f"intake file is not a Signal record: {relative_path}")
    if (
        record.get("assessment") != "observed"
        or record.get("lifecycle") != "untriaged"
        or record.get("approval") != "not_required"
    ):
        raise IntakeValidationError(f"intake Signal cannot carry a promoted state: {relative_path}")
    provider = record.get("provider")
    source_id = record.get("source_id")
    source_identity = record.get("source_identity")
    digest = record.get("payload_digest")
    sources = record.get("sources")
    if not isinstance(sources, list) or len(sources) != 1 or not isinstance(sources[0], dict):
        raise IntakeValidationError(f"Signal must retain exactly one source snapshot: {relative_path}")
    source = sources[0]
    repository_value = source.get("repository", "")
    if not isinstance(repository_value, str):
        raise IntakeValidationError(f"Signal repository identity is invalid: {relative_path}")
    repository = repository_value.strip().lower()
    expected_identity = (
        ":".join((provider, repository, source_id))
        if isinstance(provider, str) and isinstance(source_id, str)
        else None
    )
    if (
        not isinstance(provider, str)
        or not provider
        or provider != provider.lower()
        or not isinstance(source_id, str)
        or not source_id
        or not isinstance(source_identity, str)
        or source_identity != expected_identity
        or not isinstance(digest, str)
        or not DIGEST_PATTERN.fullmatch(digest)
    ):
        raise IntakeValidationError(f"Signal source identity or body digest is invalid: {relative_path}")
    expected_id = "sig-" + hashlib.sha256(
        (source_identity + ":" + digest).encode("utf-8")
    ).hexdigest()[:24]
    if record.get("id") != expected_id or relative_path != f"knowledge/inbox/{expected_id}.json":
        raise IntakeValidationError(f"Signal ID does not match its source identity and body digest: {relative_path}")
    if (
        source.get("trust_level") != "untrusted_source"
        or source.get("source_id") != source_id
        or source.get("repository", "").strip().lower() != repository
        or not isinstance(source.get("uri"), str)
        or not source["uri"].startswith(("https://", "http://"))
    ):
        raise IntakeValidationError(f"Signal source provenance is missing or trusted incorrectly: {relative_path}")


def validate_blob_modes(head_ref: str, paths: Iterable[str]) -> None:
    for path in paths:
        raw = git("ls-tree", "-r", "-z", head_ref, "--", path, binary=True)
        entries = [entry for entry in raw.split(b"\0") if entry]
        if len(entries) != 1:
            raise IntakeValidationError(f"intake path does not resolve to one Git tree entry: {path}")
        metadata, separator, entry_path = entries[0].partition(b"\t")
        if not separator or entry_path.decode("utf-8", errors="strict") != path:
            raise IntakeValidationError(f"intake path has an invalid Git tree entry: {path}")
        fields = metadata.decode("ascii").split()
        if len(fields) != 3 or fields[0] != "100644" or fields[1] != "blob":
            raise IntakeValidationError(f"intake path must be a regular non-executable file: {path}")


def workspace_path(relative: str) -> Path:
    candidate = ROOT.joinpath(*PurePosixPath(relative).parts)
    if candidate.is_symlink():
        raise IntakeValidationError(f"refusing to overwrite a symbolic link: {relative}")
    if not candidate.parent.resolve().is_relative_to(ROOT.resolve()):
        raise IntakeValidationError(f"intake path escapes repository: {relative}")
    parent = candidate.parent
    while parent != ROOT and parent != parent.parent:
        if parent.is_symlink():
            raise IntakeValidationError(f"refusing a symbolic-link parent: {parent}")
        parent = parent.parent
    return candidate


def parse_name_status_z(output: str) -> list[tuple[str, str]]:
    tokens = output.split("\0")
    changes: list[tuple[str, str]] = []
    cursor = 0
    while cursor < len(tokens) and tokens[cursor]:
        status = tokens[cursor]
        cursor += 1
        if cursor >= len(tokens) or not tokens[cursor]:
            raise IntakeValidationError("malformed Git diff name-status output")
        changes.append((status, tokens[cursor]))
        cursor += 1
    return changes


def run_trusted_validation() -> None:
    for command in (
        ("tools/egm_knowledge.py", "validate"),
        ("tools/egm_knowledge.py", "index", "--check"),
    ):
        result = subprocess.run(
            [sys.executable, *command],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise IntakeValidationError(
                result.stderr.strip()
                or result.stdout.strip()
                or f"trusted validation failed: {command}"
            )


def validate_intake_pr(
    pr_number: int,
    base_ref: str,
    head_ref: str,
    head_sha: str,
    default_branch: str,
    current_ref: str,
) -> dict[str, object]:
    if pr_number < 1:
        raise IntakeValidationError("PR number must be positive")
    base_ref = validate_ref_name(base_ref, "base_ref")
    head_ref = validate_ref_name(head_ref, "head_ref")
    if base_ref != default_branch or current_ref != default_branch:
        raise IntakeValidationError("intake validation must execute from trusted default-branch code")
    if not HEAD_REF_PATTERN.fullmatch(head_ref):
        raise IntakeValidationError("head_ref is not an EGM automation intake branch")
    if not HEAD_SHA_PATTERN.fullmatch(head_sha):
        raise IntakeValidationError("head_sha must be a full lowercase commit SHA")

    git(
        "fetch", "--no-tags", "origin",
        f"+refs/heads/{base_ref}:refs/remotes/origin/{base_ref}",
        f"+refs/heads/{head_ref}:refs/remotes/origin/{head_ref}",
    )
    base = f"refs/remotes/origin/{base_ref}"
    head = f"refs/remotes/origin/{head_ref}"
    if str(git("rev-parse", head)).strip() != head_sha:
        raise IntakeValidationError("intake PR head changed after dispatch; refusing stale validation")

    all_changes = parse_name_status_z(str(git(
        "diff", "--no-renames", "--name-status", "-z", f"{base}...{head}"
    )))
    signal_paths, index_path = validate_change_set(all_changes)
    violations = validate_changes(base, head)
    if violations:
        summary = "; ".join(
            f"{status} {path}: {reason}" for status, path, reason in violations
        )
        raise IntakeValidationError("append-only knowledge guard failed: " + summary)

    materialized = [*signal_paths, index_path]
    validate_blob_modes(head, materialized)

    for relative in signal_paths:
        destination = workspace_path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise IntakeValidationError(f"Signal path already exists in trusted base: {relative}")
        content = git("show", f"{head}:{relative}", binary=True)
        validate_signal_record(relative, content)
        with destination.open("xb") as output:
            output.write(content)

    index_destination = workspace_path(index_path)
    index_content = git("show", f"{head}:{index_path}", binary=True)
    index_destination.write_bytes(index_content)

    # Execute only trusted default-branch code; PR blobs were materialized as data.
    run_trusted_validation()
    return {
        "pr_number": pr_number,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "head_sha": head_sha,
        "signal_files": len(signal_paths),
        "status": "validated_data_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--default-branch", required=True)
    parser.add_argument("--current-ref", required=True)
    args = parser.parse_args()
    try:
        result = validate_intake_pr(
            args.pr_number, args.base_ref, args.head_ref, args.head_sha,
            args.default_branch, args.current_ref,
        )
    except (OSError, IntakeValidationError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
