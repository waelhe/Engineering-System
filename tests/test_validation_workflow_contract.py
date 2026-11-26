from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_knowledge_validation_cancels_superseded_pull_request_runs():
    workflow = (ROOT / ".github" / "workflows" / "knowledge-validation.yml").read_text(encoding="utf-8")
    assert "concurrency:" in workflow
    assert "github.event.pull_request.number || github.run_id" in workflow
    assert "cancel-in-progress: true" in workflow


def test_cross_repository_collector_is_manual_or_scheduled_and_never_checks_out_source_code():
    workflow = (ROOT / ".github" / "workflows" / "cross-repository-review-intake.yml").read_text(encoding="utf-8")
    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "actions/checkout@" in workflow
    assert "EGM_SOURCE_GITHUB_TOKEN" in workflow
    assert "GITHUB_TOKEN: ${{ github.token }}" in workflow
    assert "permission-pull-requests: read" in workflow
    assert "permission-issues: read" in workflow
    assert "permission-contents: write" not in workflow


def test_governance_audit_has_separate_sink_and_read_only_source_tokens():
    workflow = (ROOT / ".github" / "workflows" / "repository-governance-audit.yml").read_text(encoding="utf-8")
    assert "EGM_SOURCE_GITHUB_TOKEN" in workflow
    assert "GITHUB_TOKEN: ${{ github.token }}" in workflow
    assert "permission-pull-requests: read" in workflow
    assert "permission-issues: read" in workflow
    assert "permission-administration: write" not in workflow
