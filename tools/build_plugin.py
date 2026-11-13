#!/usr/bin/env python3
"""Assemble one EGM runtime from the pinned upstream and local extensions."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream" / "egm"
LOCK = ROOT / "upstream" / "egm.lock.json"
EXTENSIONS = ROOT / "extensions"
LOCAL_NAME = "EGM Engineering System"
LOCAL_VERSION = "0.1.0"


def load_lock() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def checked_upstream_commit() -> str:
    if not UPSTREAM.is_dir():
        raise RuntimeError("EGM submodule is missing; run git submodule update --init --recursive")
    result = subprocess.run(
        ["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def update_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["name"] = "egm-engineering-system"
    manifest["version"] = LOCAL_VERSION
    manifest["description"] = "An evidence-backed engineering operating system built on EGM."
    manifest["author"] = {"name": LOCAL_NAME}
    manifest["repository"] = "https://github.com/waelhe/Engineering-System"
    manifest["homepage"] = "https://github.com/waelhe/Engineering-System"
    manifest["license"] = "Apache-2.0"

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        interface = manifest.get("extensions", {}).get("com.openai", {}).get("interface")
    if isinstance(interface, dict):
        interface["displayName"] = LOCAL_NAME
        interface["shortDescription"] = "Design, build, verify and learn with evidence"
        interface["longDescription"] = (
            "A unified engineering system built on the pinned Elephant-Goldfish Model. "
            "It combines task-scoped project context, structured engineering knowledge, "
            "independent design review, controlled implementation, SHA-bound verification "
            "and evidence-backed learning. Human approval remains required at authority boundaries."
        )
        interface["developerName"] = LOCAL_NAME
        interface["capabilities"] = [
            "Engineering task orchestration",
            "Evidence-backed project knowledge",
            "Independent design review",
            "Controlled implementation and verification",
            "Closed-loop engineering learning",
        ]
        interface["defaultPrompt"] = [
            "Classify this engineering task and retrieve the relevant project knowledge.",
            "Review this engineering design independently before implementation.",
            "Verify this change against its plan, tests and exact commit SHA.",
        ]
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def copy_overlay(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target)


def assemble(target: str, output: Path) -> tuple[Path, Path]:
    lock = load_lock()
    actual = checked_upstream_commit()
    expected = lock["baseline"]["commit"]
    if actual != expected:
        raise RuntimeError(
            f"Upstream EGM is not pinned baseline: expected {expected}, found {actual}. "
            "Do not build from an unreviewed upstream revision."
        )
    output = output.resolve()
    if output.exists():
        raise RuntimeError(f"Output already exists: {output}")

    with tempfile.TemporaryDirectory(prefix="egm-system-build-") as temporary:
        stage = Path(temporary) / "source"
        shutil.copytree(
            UPSTREAM,
            stage,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv"),
        )
        copy_overlay(EXTENSIONS / "skills", stage / "skills")
        copy_overlay(EXTENSIONS / "agents", stage / "agents")
        copy_overlay(EXTENSIONS / "resources", stage / "resources")

        policy_map = {
            "engineering-charter.md": ROOT / "docs/policies/engineering-charter.md",
            "task-risk.md": ROOT / "docs/policies/task-risk.md",
            "retrieval.md": ROOT / "docs/policies/retrieval.md",
            "review-policy.md": ROOT / "docs/policies/review.md",
            "verification-policy.md": ROOT / "docs/policies/verification.md",
            "knowledge-learning.md": ROOT / "docs/policies/knowledge-learning.md",
            "system-architecture.md": ROOT / "docs/architecture/system-architecture.md",
            "knowledge-model.md": ROOT / "docs/architecture/knowledge-model.md",
            "knowledge-lifecycle.md": ROOT / "docs/architecture/knowledge-lifecycle.md",
        }
        for name, source in policy_map.items():
            shutil.copy2(source, stage / "resources" / name)

        update_manifest(stage / "plugin.json")
        update_manifest(stage / ".codex-plugin" / "plugin.json")
        claude_manifest = stage / ".claude-plugin" / "plugin.json"
        if claude_manifest.is_file():
            update_manifest(claude_manifest)

        packer = stage / "scripts" / "pack_plugin.py"
        if not packer.is_file():
            raise RuntimeError("Pinned EGM packaging script is missing")
        result = subprocess.run(
            [sys.executable, str(packer), "--target", target, "--output", str(output)],
            check=False, capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "EGM package build failed")
        print(result.stdout.strip())

    runtime = output / f"egm-{target}"
    archive = output / f"egm-{target}.zip"
    if not runtime.is_dir() or not archive.is_file():
        raise RuntimeError("Upstream packer returned success without both runtime folder and ZIP")
    return runtime, archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("openai", "claude"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        runtime, archive = assemble(args.target, args.output)
    except (OSError, KeyError, json.JSONDecodeError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Integrated runtime: {runtime}")
    print(f"Package archive: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
