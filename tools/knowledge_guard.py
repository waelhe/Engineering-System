#!/usr/bin/env python3
"""Enforce immutable source records and append-only JSONL evidence batches."""

from __future__ import annotations

import argparse
import subprocess
import sys


APPEND_ONLY_PREFIXES = ("knowledge/inbox/", "knowledge/evidence/")


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args], check=False, capture_output=True
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip() or f"git {' '.join(args)} failed")
    return result.stdout


def changed_paths(base: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "diff", "--name-status", "-z", f"{base}...HEAD", "--", *APPEND_ONLY_PREFIXES],
        check=False, capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip() or "git diff failed")
    tokens = result.stdout.split(b"\0")
    changes: list[tuple[str, str]] = []
    index = 0
    while index < len(tokens) and tokens[index]:
        status = tokens[index].decode("ascii")
        index += 1
        if status.startswith(("R", "C")):
            old_path = tokens[index].decode("utf-8", errors="surrogateescape")
            new_path = tokens[index + 1].decode("utf-8", errors="surrogateescape")
            index += 2
            changes.extend([(status, old_path), (status, new_path)])
        else:
            path = tokens[index].decode("utf-8", errors="surrogateescape")
            index += 1
            changes.append((status, path))
    return changes


def is_append_only_jsonl_update(base: str, path: str) -> bool:
    if not path.endswith(".jsonl"):
        return False
    try:
        before = git_bytes("show", f"{base}:{path}").splitlines()
        after = git_bytes("show", f"HEAD:{path}").splitlines()
    except RuntimeError:
        return False
    if not before or not after or len(after) < len(before):
        return False
    # Preserve every historical non-empty record byte-for-byte and in order.
    old_records = [line for line in before if line.strip()]
    new_records = [line for line in after if line.strip()]
    return len(new_records) >= len(old_records) and new_records[:len(old_records)] == old_records


def validate_changes(base: str) -> list[tuple[str, str, str]]:
    violations: list[tuple[str, str, str]] = []
    for status, path in changed_paths(base):
        if status == "A":
            continue
        if status == "M" and is_append_only_jsonl_update(base, path):
            continue
        violations.append((status, path, "only new files or byte-preserving JSONL appends are allowed"))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base branch ref, e.g. origin/main")
    args = parser.parse_args()
    try:
        violations = validate_changes(args.base)
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if violations:
        for status, path, reason in violations:
            print(f"append-only violation: {status} {path}: {reason}", file=sys.stderr)
        return 1
    print("Append-only Signal/Evidence history: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
