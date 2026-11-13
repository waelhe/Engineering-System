#!/usr/bin/env python3
"""Enforce append-only history for raw Signal and Evidence records."""

from __future__ import annotations

import argparse
import subprocess
import sys


APPEND_ONLY_PREFIXES = ("knowledge/inbox/", "knowledge/evidence/")


def changed_paths(base: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "diff", "--name-status", "-z", f"{base}...HEAD", "--", *APPEND_ONLY_PREFIXES],
        check=False, capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    tokens = result.stdout.split("\0")
    changes: list[tuple[str, str]] = []
    index = 0
    while index < len(tokens) and tokens[index]:
        status = tokens[index]
        index += 1
        if status.startswith(("R", "C")):
            old_path = tokens[index]
            new_path = tokens[index + 1]
            index += 2
            changes.append((status, old_path))
            changes.append((status, new_path))
        else:
            path = tokens[index]
            index += 1
            changes.append((status, path))
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="merge base ref, e.g. origin/main")
    args = parser.parse_args()
    try:
        violations = [(status, path) for status, path in changed_paths(args.base) if status != "A"]
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if violations:
        for status, path in violations:
            print(f"append-only violation: {status} {path}", file=sys.stderr)
        return 1
    print("Append-only Signal/Evidence history: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
