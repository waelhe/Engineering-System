from __future__ import annotations
import json
import subprocess

import pytest
from urllib.parse import parse_qs, urlsplit
import tools.github_review_intake as intake

def test_api_pages_reads_all_pages(monkeypatch):
    calls=[]
    def fake(method,path,token,payload=None):
        calls.append(path)
        page=int(parse_qs(urlsplit(path).query)["page"][0])
        return [{"id":page*100+i} for i in range(100 if page==1 else 2)]
    monkeypatch.setattr(intake,"api_request",fake)
    assert len(intake.api_pages("/repos/owner/repo/pulls/1/reviews","token"))==102
    assert len(calls)==2

def test_workflow_run_accepts_only_trusted_capture_and_deduplicates_pr_numbers(monkeypatch):
    def fake(method, path, token, payload=None):
        if path.endswith("/actions/workflows/review-signal-capture.yml"):
            return {"id": 700}
        return {"name":intake.CAPTURE_WORKFLOW,"workflow_id":700,
            "path":".github/workflows/review-signal-capture.yml","event":"pull_request_review",
            "status":"completed","conclusion":"success",
            "repository":{"full_name":"owner/repo"},"pull_requests":[{"number":42},{"number":42},{"number":43}]}
    monkeypatch.setattr(intake,"api_request",fake)
    assert intake.resolve_pr_numbers("owner/repo","token","workflow_run",
        {"workflow_run":{"id":17}},None,7,50)==[42,43]

@pytest.mark.parametrize(
    ("changed", "message"),
    [
        ({"workflow_id": 701}, "workflow ID mismatch"),
        ({"path": ".github/workflows/untrusted.yml"}, "path does not match"),
        ({"event": "push"}, "not an allowed review signal event"),
        ({"repository": {"full_name": "attacker/repo"}}, "another repository"),
    ],
)
def test_workflow_run_rejects_each_trust_boundary_independently(monkeypatch, changed, message):
    trusted_run = {
        "name": intake.CAPTURE_WORKFLOW,
        "workflow_id": 700,
        "path": ".github/workflows/review-signal-capture.yml",
        "event": "pull_request_review",
        "status": "completed",
        "conclusion": "success",
        "repository": {"full_name": "owner/repo"},
        "pull_requests": [{"number": 12}],
    }

    def fake(method, path, token, payload=None):
        if path.endswith("/actions/workflows/review-signal-capture.yml"):
            return {"id": 700}
        return {**trusted_run, **changed}

    monkeypatch.setattr(intake, "api_request", fake)
    with pytest.raises(intake.IntakeError, match=message):
        intake.resolve_pr_numbers(
            "owner/repo", "token", "workflow_run",
            {"workflow_run": {"id": 5}}, None, 7, 50,
        )


def test_prepare_branch_starts_only_from_trusted_default_branch(monkeypatch):
    calls = []

    def fake_api(method, path, token, payload=None):
        assert method == "GET"
        assert path == "/repos/owner/repo"
        return {"default_branch": "main"}

    monkeypatch.setattr(intake, "api_request", fake_api)
    monkeypatch.setattr(intake, "git", lambda *args, **kwargs: calls.append(args))
    branch, base = intake.prepare_branch("owner/repo", "secret", "12345", "2")

    assert branch == "automation/knowledge-intake-12345-2"
    assert base == "main"
    assert ("checkout", "-B", branch, "refs/remotes/origin/main") in calls
    assert not any("pulls?state=open" in " ".join(call) for call in calls)
    assert not any(call[0] == "merge" for call in calls)
    assert calls.index(("config", "user.name", "EGM Knowledge Intake Bot")) < calls.index(
        ("checkout", "-B", branch, "refs/remotes/origin/main")
    )


def test_child_environment_drops_github_credentials(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-leak")
    monkeypatch.setenv("GH_TOKEN", "must-not-leak-either")
    environment = intake.unprivileged_child_environment()
    assert "GITHUB_TOKEN" not in environment
    assert "GH_TOKEN" not in environment


def test_source_payload_redacts_secrets_before_its_size_limit():
    private_key = (
        "-----BEGIN PRIVATE KEY-----\\n"
        + ("SOURCE-PAYLOAD-SECRET-" * 1000)
        + "\\n-----END PRIVATE KEY-----"
    )
    review = {
        "id": 102,
        "body": ("x" * (intake.MAX_SOURCE_BODY - 2000)) + private_key,
        "user": {"login": "reviewer"},
        "created_at": "2026-11-14T00:00:00Z",
    }

    payload = intake.source_payload(
        "owner/repo", "sample-project", {"number": 9},
        review, "github_review", "workflow_run",
    )

    assert "SOURCE-PAYLOAD-SECRET" not in payload["body"]
    assert "BEGIN PRIVATE KEY" not in payload["body"]



def test_publish_batch_defers_when_same_signal_is_in_a_pending_intake_pr(monkeypatch):
    calls = []

    def fake_git(*args, **kwargs):
        calls.append(args)
        if args[:3] == ("diff", "--cached", "--quiet"):
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
        if args[:3] == ("diff", "--cached", "--name-only"):
            return subprocess.CompletedProcess(
                args, 0, stdout="knowledge/inbox/sig-same-snapshot.json\\0", stderr=""
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    def fake_api_pages(path, token):
        if path.startswith("/repos/owner/repo/pulls?"):
            return [{
                "number": 17,
                "draft": True,
                "base": {"ref": "main", "repo": {"full_name": "owner/repo"}},
                "head": {"ref": "automation/knowledge-intake-123-1", "repo": {"full_name": "owner/repo"}},
            }]
        if path == "/repos/owner/repo/pulls/17/files":
            return [{"filename": "knowledge/inbox/sig-same-snapshot.json"}]
        raise AssertionError(f"unexpected API page: {path}")

    monkeypatch.setattr(intake, "git", fake_git)
    monkeypatch.setattr(intake, "api_pages", fake_api_pages)

    result = intake.publish_batch("owner/repo", "token", "automation/knowledge-intake-456-1", "main")

    assert result == {
        "deferred": True,
        "reason": "equivalent_signal_batch_pending",
        "overlapping_signal_count": 1,
    }
    assert not any(args and args[0] in {"commit", "push"} for args in calls)


def test_pending_intake_pr_does_not_suppress_unrelated_signal_paths(monkeypatch):
    pages = {
        "/repos/owner/repo/pulls?state=open&sort=created&direction=desc": [{
            "number": 18,
            "draft": True,
            "base": {"ref": "main", "repo": {"full_name": "owner/repo"}},
            "head": {"ref": "automation/knowledge-intake-123-1", "repo": {"full_name": "owner/repo"}},
        }],
        "/repos/owner/repo/pulls/18/files": [
            {"filename": "knowledge/inbox/sig-another-snapshot.json"}
        ],
    }

    monkeypatch.setattr(intake, "api_pages", lambda path, token: pages[path])

    pending = intake.pending_intake_signal_paths("owner/repo", "token", "main")

    assert pending == {"knowledge/inbox/sig-another-snapshot.json"}



def test_review_signal_binds_author_sha_and_source_link():
    review={"id":101,"state":"CHANGES_REQUESTED","body":"Please fix this.",
        "html_url":"https://github.com/owner/repo/pull/9#pullrequestreview-101",
        "user":{"login":"reviewer"},"author_association":"MEMBER",
        "submitted_at":"2026-11-13T20:00:00Z","commit_id":"b"*40}
    payload=intake.source_payload("owner/repo","sample-project",{"number":9},review,"github_review","workflow_run")
    assert payload["source_id"]=="github_review-101" and payload["source_actor"]=="reviewer"
    assert payload["commit_sha"]=="b"*40
    assert json.loads(payload["body"])["state"]=="CHANGES_REQUESTED"
