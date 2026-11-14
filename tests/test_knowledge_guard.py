import subprocess
from pathlib import Path

from tools.knowledge_guard import changed_paths, validate_changes


def git(root: Path, *args: str):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def init_repo(root: Path):
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    (root / "knowledge/inbox").mkdir(parents=True)
    (root / "knowledge/evidence").mkdir(parents=True)


def test_append_only_guard_rejects_mutating_raw_json_and_allows_new_records(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    init_repo(root)
    monkeypatch.chdir(root)
    (root / "knowledge/inbox/signal-old.json").write_text("{}", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline")
    base = git(root, "rev-parse", "HEAD").stdout.strip()
    (root / "knowledge/inbox/signal-new.json").write_text("{}", encoding="utf-8")
    (root / "knowledge/inbox/signal-old.json").write_text('{"changed":true}', encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "new and mutate")
    changes = changed_paths(base)
    assert ("A", "knowledge/inbox/signal-new.json") in changes
    assert ("M", "knowledge/inbox/signal-old.json") in changes
    assert validate_changes(base) == [("M", "knowledge/inbox/signal-old.json", "only new files or byte-preserving JSONL appends are allowed")]


def test_append_only_guard_allows_jsonl_append_but_rejects_rewrite_or_reorder(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    init_repo(root)
    monkeypatch.chdir(root)
    batch = root / "knowledge/evidence/history.jsonl"
    batch.write_text('{"id":"e1"}\n{"id":"e2"}\n', encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline")
    base = git(root, "rev-parse", "HEAD").stdout.strip()

    batch.write_text('{"id":"e1"}\n{"id":"e2"}\n{"id":"e3"}\n', encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "append only")
    assert validate_changes(base) == []

    append_base = git(root, "rev-parse", "HEAD").stdout.strip()
    batch.write_text('{"id":"e1-modified"}\n{"id":"e2"}\n{"id":"e3"}\n', encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "rewrite historic evidence")
    assert validate_changes(append_base)


def test_append_only_guard_rejects_deleting_jsonl_records(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    init_repo(root)
    monkeypatch.chdir(root)
    batch = root / "knowledge/evidence/history.jsonl"
    batch.write_text('{"id":"e1"}\n{"id":"e2"}\n', encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "baseline")
    base = git(root, "rev-parse", "HEAD").stdout.strip()
    batch.write_text('{"id":"e1"}\n', encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "delete evidence")
    assert validate_changes(base)
