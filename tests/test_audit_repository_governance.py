from __future__ import annotations

import json

import pytest

import tools.audit_repository_governance as audit


def policy(required_checks=None):
    return {
        "schema_version": 1,
        "repositories": [
            {
                "repository": "owner/repo",
                "default_branch": "main",
                "expected": {
                    "required_rules": [
                        "deletion",
                        "non_fast_forward",
                        "required_linear_history",
                        "pull_request",
                        "required_status_checks",
                    ],
                    "required_approving_review_count": 0,
                    "require_thread_resolution": True,
                    "required_merge_methods": ["squash"],
                    "required_status_checks": required_checks if required_checks is not None else ["validate"],
                },
            }
        ],
    }


def matching_ruleset(checks=None):
    return {
        "id": 5,
        "name": "main governance",
        "target": "branch",
        "enforcement": "active",
        "source": "owner/repo",
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "required_linear_history"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 0,
                    "required_review_thread_resolution": True,
                    "allowed_merge_methods": ["squash"],
                },
            },
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [
                        {"context": name, "app_id": 15368}
                        for name in (checks if checks is not None else ["validate"])
                    ]
                },
            },
        ],
    }


def test_load_policy_requires_unique_repository_and_explicit_checks(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy()), encoding="utf-8")
    loaded = audit.load_policy(path)
    assert loaded["repositories"][0]["repository"] == "owner/repo"

    invalid = policy() | {"repositories": policy()["repositories"] * 2}
    path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(audit.GovernanceAuditError, match="Duplicate repository"):
        audit.load_policy(path)


def test_audit_repository_verifies_exact_active_branch_policy(monkeypatch):
    details = matching_ruleset()
    calls = []

    def fake_api(path, token):
        calls.append(path)
        if path.endswith("/branches/main"):
            return {"name": "main", "protected": True}
        if path.endswith("/rulesets?includes_parents=true"):
            return [{"id": 5, "target": "branch", "enforcement": "active"}]
        if path.endswith("/rulesets/5"):
            return details
        raise AssertionError(path)

    monkeypatch.setattr(audit, "api_get", fake_api)
    result = audit.audit_repository(policy()["repositories"][0], "read-only-token")

    assert result["status"] == "verified"
    assert result["active_rulesets"] == [
        {"id": 5, "name": "main governance", "source": "owner/repo"}
    ]
    assert result["observed_status_checks"] == ["validate"]
    assert calls == [
        "/repos/owner/repo/branches/main",
        "/repos/owner/repo/rulesets?includes_parents=true",
        "/repos/owner/repo/rulesets/5",
    ]


def test_audit_repository_reports_missing_required_check(monkeypatch):
    details = matching_ruleset(checks=["different-check"])

    def fake_api(path, token):
        if path.endswith("/branches/main"):
            return {"protected": True}
        if path.endswith("/rulesets?includes_parents=true"):
            return [{"id": 5, "target": "branch", "enforcement": "active"}]
        if path.endswith("/rulesets/5"):
            return details
        raise AssertionError(path)

    monkeypatch.setattr(audit, "api_get", fake_api)
    result = audit.audit_repository(policy()["repositories"][0], "read-only-token")

    assert result["status"] == "policy_gap"
    assert result["missing_status_checks"] == ["validate"]
    assert result["missing_rules"] == []


def test_audit_repository_does_not_call_plan_limited_private_repo_unprotected(monkeypatch):
    def fake_api(path, token):
        if path.endswith("/branches/main"):
            return {"protected": False}
        raise audit.GovernanceApiError(
            403,
            "Upgrade to GitHub Pro or make this repository public to enable this feature.",
        )

    monkeypatch.setattr(audit, "api_get", fake_api)
    result = audit.audit_repository(policy()["repositories"][0], "read-only-token")

    assert result["status"] == "plan_limited"
    assert result["branch_protected"] is False
    assert result["missing_rules"] == []


def test_audit_repository_distinguishes_unreadable_classic_protection(monkeypatch):
    def fake_api(path, token):
        if path.endswith("/branches/main"):
            return {"protected": True}
        if path.endswith("/rulesets?includes_parents=true"):
            return []
        raise AssertionError(path)

    monkeypatch.setattr(audit, "api_get", fake_api)
    result = audit.audit_repository(policy()["repositories"][0], "read-only-token")

    assert result["status"] == "protected_but_details_unavailable"
    assert "classic protection details" in result["reason"]


def test_audit_repository_ignores_non_matching_inactive_ruleset(monkeypatch):
    inactive = matching_ruleset()
    inactive["enforcement"] = "disabled"

    def fake_api(path, token):
        if path.endswith("/branches/main"):
            return {"protected": False}
        if path.endswith("/rulesets?includes_parents=true"):
            return [inactive]
        raise AssertionError(path)

    monkeypatch.setattr(audit, "api_get", fake_api)
    result = audit.audit_repository(policy()["repositories"][0], "read-only-token")

    assert result["status"] == "policy_gap"
    assert "required_status_checks" in result["missing_rules"]
