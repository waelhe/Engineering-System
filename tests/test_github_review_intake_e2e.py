from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import tools.egm_knowledge as knowledge
import tools.github_review_intake as intake


REPO = Path(__file__).resolve().parents[1]


def test_workflow_dispatch_collects_validates_and_publishes_one_data_only_signal(
    tmp_path, monkeypatch, capsys
):
    """Exercise the collector's full local lifecycle without live credentials or GitHub writes."""
    root = tmp_path / "checkout"
    (root / "knowledge" / "projects").mkdir(parents=True)
    schemas = root / "schemas"
    schemas.mkdir()
    for name in (
        "knowledge-record.schema.json",
        "project-profile.schema.json",
        "execution-receipt.schema.json",
    ):
        shutil.copy(REPO / "schemas" / name, schemas / name)
    for folder in knowledge.RECORD_DIRS:
        (root / "knowledge" / folder).mkdir(parents=True, exist_ok=True)

    profile = {
        "schema_version": 1,
        "project_id": "sample-project",
        "name": "Sample Project",
        "repositories": [{"name": "owner/repo", "default_branch": "main"}],
        "technology": [],
        "module_map": [],
        "source_of_truth": ["README.md"],
    }
    (root / "knowledge/projects/sample-project.json").write_text(
        json.dumps(profile), encoding="utf-8"
    )
    monkeypatch.setattr(knowledge, "ROOT", root)
    monkeypatch.setattr(knowledge, "KNOWLEDGE", root / "knowledge")
    monkeypatch.setattr(knowledge, "SCHEMAS", schemas)
    monkeypatch.setattr(knowledge, "RECORD_SCHEMA", schemas / "knowledge-record.schema.json")
    monkeypatch.setattr(knowledge, "PROFILE_SCHEMA", schemas / "project-profile.schema.json")
    monkeypatch.setattr(knowledge, "RECEIPT_SCHEMA", schemas / "execution-receipt.schema.json")
    monkeypatch.chdir(root)

    event_file = root / "event.json"
    event_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "destination-write-token")
    monkeypatch.setenv("EGM_PROJECT_ID", "sample-project")

    now = datetime.now(timezone.utc).isoformat()
    open_pr = {
        "number": 7,
        "updated_at": now,
        "base": {"ref": "main", "repo": {"full_name": "owner/repo"}},
        "head": {"ref": "feature/reviewed-change", "sha": "a" * 40},
    }
    review = {
        "id": 501,
        "state": "CHANGES_REQUESTED",
        "body": "Add a regression test for the reported boundary condition.",
        "html_url": "https://github.com/owner/repo/pull/7#pullrequestreview-501",
        "user": {"login": "reviewer"},
        "author_association": "MEMBER",
        "submitted_at": now,
        "created_at": now,
        "updated_at": now,
        "commit_id": "a" * 40,
    }
    api_calls = []
    git_calls = []
    child_commands = []
    dispatched = []
    pushed = []

    def fake_api_request(method, path, token, payload=None):
        api_calls.append((method, path, token, payload))
        if method == "GET" and path == "/repos/owner/repo":
            return {"default_branch": "main"}
        if method == "GET" and path == "/repos/owner/repo/pulls/7":
            return {
                "number": 7,
                "base": {"repo": {"full_name": "owner/repo"}, "ref": "main"},
                "head": {"repo": {"full_name": "owner/repo"}, "ref": "feature/reviewed-change"},
            }
        if method == "POST" and path == "/repos/owner/repo/pulls":
            return {
                "number": 99,
                "html_url": "https://github.com/owner/repo/pull/99",
                "head": {"ref": payload["head"], "sha": "c" * 40},
                "base": {"ref": payload["base"]},
            }
        if method == "POST" and path.endswith(
            "/actions/workflows/knowledge-validation.yml/dispatches"
        ):
            dispatched.append(payload)
            return None
        raise AssertionError(f"unexpected GitHub API request: {method} {path}")

    def fake_api_pages(path, token):
        if "/pulls?state=open&sort=updated" in path:
            return [open_pr]
        if path == "/repos/owner/repo/pulls/7/reviews":
            return [review]
        if path == "/repos/owner/repo/pulls/7/comments":
            return []
        if path == "/repos/owner/repo/issues/7/comments":
            return []
        if "/pulls?state=open&sort=created" in path:
            return []
        raise AssertionError(f"unexpected paginated GitHub API request: {path}")

    def fake_git(*args, check=True):
        git_calls.append(args)
        if args[:3] == ("diff", "--cached", "--quiet"):
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
        if args[:3] == ("diff", "--cached", "--name-only"):
            signal_paths = sorted((root / "knowledge/inbox").glob("*.json"))
            names = "".join(
                f"knowledge/inbox/{path.name}\0" for path in signal_paths
            )
            return subprocess.CompletedProcess(args, 0, stdout=names, stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    def fake_run_trusted_python(*args):
        child_commands.append(args)
        if args == ("tools/egm_knowledge.py", "validate"):
            assert knowledge.validate_all() == []
        elif args == ("tools/validate_migration.py",):
            # Migration provenance is validated by the repository CI workflow;
            # this isolated fixture deliberately contains no migration manifest.
            return
        elif args == ("tools/egm_knowledge.py", "index"):
            knowledge.write_index()
        elif args == ("tools/egm_knowledge.py", "validate-receipts"):
            assert knowledge.validate_receipts() == []
        elif args == ("-m", "pytest", "-q"):
            return
        else:
            raise AssertionError(f"unexpected trusted child command: {args}")

    monkeypatch.setattr(intake, "api_request", fake_api_request)
    monkeypatch.setattr(intake, "api_pages", fake_api_pages)
    monkeypatch.setattr(intake, "git", fake_git)
    monkeypatch.setattr(intake, "git_with_token", lambda args, token: git_calls.append(tuple(args)))
    monkeypatch.setattr(intake, "git_push", lambda branch_name, token: pushed.append(branch_name))
    monkeypatch.setattr(intake, "run_trusted_python", fake_run_trusted_python)

    result = intake.main([
        "--event-file", str(event_file),
        "--event-name", "workflow_dispatch",
        "--run-id", "12345",
        "--run-attempt", "2",
    ])

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["selected_prs"] == [7]
    assert output["totals"] == {"created": 1, "duplicate": 0, "objects": 1, "prs": 1}
    assert output["publication"]["number"] == 99
    assert output["publication"]["validation"]["status"] == "dispatched"

    signals = sorted((root / "knowledge/inbox").glob("*.json"))
    assert len(signals) == 1
    stored = json.loads(signals[0].read_text(encoding="utf-8"))
    assert stored["project_id"] == "sample-project"
    assert stored["source_id"] == "github_review-501"
    assert stored["sources"][0]["commit_sha"] == "a" * 40
    assert stored["lifecycle"] == "untriaged"
    assert (root / "knowledge/index.json").is_file()

    staged = next(args for args in git_calls if args and args[0] == "add")
    assert staged == ("add", "--", "knowledge/inbox", "knowledge/index.json")
    assert pushed == ["automation/knowledge-intake-12345-2"]
    assert len(dispatched) == 1
    assert dispatched[0] == {
        "ref": "main",
        "inputs": {
            "intake_pr_number": "99",
            "intake_head_ref": "automation/knowledge-intake-12345-2",
            "intake_head_sha": "c" * 40,
            "intake_base_ref": "main",
        },
    }
    assert [command for command in child_commands if command == ("tools/egm_knowledge.py", "validate")]
    assert child_commands.index(("tools/egm_knowledge.py", "validate")) < child_commands.index(
        ("tools/egm_knowledge.py", "index")
    )
    assert all(call[2] == "destination-write-token" for call in api_calls)
