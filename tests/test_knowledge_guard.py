import subprocess
from pathlib import Path

from tools.knowledge_guard import changed_paths


def git(root: Path, *args: str):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def test_append_only_diff_reports_added_and_modified_paths(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    monkeypatch.chdir(root)
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    (root / "knowledge/inbox").mkdir(parents=True)
    (root / "knowledge/evidence").mkdir(parents=True)
    (root / "knowledge/inbox/signal-old.json").write_text("{}", encoding="utf-8")
    (root / "knowledge/evidence/evidence-old.json").write_text("{}", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline")
    base = git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "knowledge/inbox/signal-new.json").write_text("{}", encoding="utf-8")
    (root / "knowledge/evidence/evidence-old.json").write_text('{"changed":true}', encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "append and mutate")
    changes = changed_paths(base)
    assert ("A", "knowledge/inbox/signal-new.json") in changes
    assert ("M", "knowledge/evidence/evidence-old.json") in changes
