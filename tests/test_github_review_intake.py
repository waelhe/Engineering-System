from __future__ import annotations
import json
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
    monkeypatch.setattr(intake,"api_request",lambda *a,**k:{
        "name":intake.CAPTURE_WORKFLOW,"status":"completed","conclusion":"success",
        "repository":{"full_name":"owner/repo"},"pull_requests":[{"number":42},{"number":42},{"number":43}]})
    assert intake.resolve_pr_numbers("owner/repo","token","workflow_run",
        {"workflow_run":{"id":17}},None,7,50)==[42,43]

def test_untrusted_workflow_run_is_rejected(monkeypatch):
    monkeypatch.setattr(intake,"api_request",lambda *a,**k:{"name":"Other Workflow","status":"completed",
        "conclusion":"success","repository":{"full_name":"owner/repo"},"pull_requests":[{"number":12}]})
    try:
        intake.resolve_pr_numbers("owner/repo","token","workflow_run",{"workflow_run":{"id":5}},None,7,50)
    except intake.IntakeError as exc:
        assert "trusted review-capture" in str(exc)
    else:
        raise AssertionError("untrusted workflow was accepted")

def test_review_signal_binds_author_sha_and_source_link():
    review={"id":101,"state":"CHANGES_REQUESTED","body":"Please fix this.",
        "html_url":"https://github.com/owner/repo/pull/9#pullrequestreview-101",
        "user":{"login":"reviewer"},"author_association":"MEMBER",
        "submitted_at":"2026-11-13T20:00:00Z","commit_id":"b"*40}
    payload=intake.source_payload("owner/repo","sample-project",{"number":9},review,"github_review","workflow_run")
    assert payload["source_id"]=="github_review-101" and payload["source_actor"]=="reviewer"
    assert payload["commit_sha"]=="b"*40
    assert json.loads(payload["body"])["state"]=="CHANGES_REQUESTED"
