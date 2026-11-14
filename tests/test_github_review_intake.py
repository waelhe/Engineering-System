from __future__ import annotations
import json

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


def test_review_signal_binds_author_sha_and_source_link():
    review={"id":101,"state":"CHANGES_REQUESTED","body":"Please fix this.",
        "html_url":"https://github.com/owner/repo/pull/9#pullrequestreview-101",
        "user":{"login":"reviewer"},"author_association":"MEMBER",
        "submitted_at":"2026-11-13T20:00:00Z","commit_id":"b"*40}
    payload=intake.source_payload("owner/repo","sample-project",{"number":9},review,"github_review","workflow_run")
    assert payload["source_id"]=="github_review-101" and payload["source_actor"]=="reviewer"
    assert payload["commit_sha"]=="b"*40
    assert json.loads(payload["body"])["state"]=="CHANGES_REQUESTED"
