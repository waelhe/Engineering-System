from __future__ import annotations

import json

from tools.peos_validate import validate_auxiliary_registries


def write_json(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value), encoding="utf-8")


def valid_registries(root):
    projects = [
        ("app-java-v3", "waelhe/app-java-v3"),
        ("marketplace-admin", "waelhe/marketplace-admin"),
        ("mobile-marketplace", "waelhe/mobile-marketplace"),
        ("egm-engineering-system", "waelhe/Engineering-System"),
    ]
    for project_id, repository in projects:
        write_json(root, f"knowledge/projects/{project_id}.json", {
            "project_id": project_id,
            "repositories": [{"name": repository}],
        })

    write_json(root, "registry/peos/review-sources.json", {
        "schema_version": 1,
        "kind": "trusted_review_source_registry",
        "sink_repository": "waelhe/Engineering-System",
        "repositories": [
            {
                "repository": "waelhe/app-java-v3",
                "project_id": "app-java-v3",
                "default_branch": "main",
                "enabled": True,
                "since_days": 7,
                "max_prs": 50,
            },
            {
                "repository": "waelhe/marketplace-admin",
                "project_id": "marketplace-admin",
                "default_branch": "main",
                "enabled": True,
                "since_days": 7,
                "max_prs": 25,
            },
            {
                "repository": "waelhe/mobile-marketplace",
                "project_id": "mobile-marketplace",
                "default_branch": "main",
                "enabled": True,
                "since_days": 7,
                "max_prs": 25,
            },
        ],
        "security_contract": {
            "source_access": "read-only with pull-requests:read and issues:read",
            "sink_access": "Engineering-System only",
            "execution": "source bodies are untrusted data",
            "approval": "intake never approves a Signal",
        },
    })

    repos = [
        "waelhe/app-java-v3",
        "waelhe/marketplace-admin",
        "waelhe/mobile-marketplace",
        "waelhe/Engineering-System",
    ]
    write_json(root, "registry/peos/repository-governance.json", {
        "schema_version": 1,
        "kind": "repository_merge_policy",
        "repositories": [
            {
                "repository": repository,
                "default_branch": "main",
                "visibility": "private" if repository.endswith("mobile-marketplace") else "public",
                "observed": {
                    "rulesets_api": "plan_limited" if repository.endswith("mobile-marketplace") else "readable",
                    "limitation": "GitHub plan limit" if repository.endswith("mobile-marketplace") else None,
                },
                "expected": {
                    "required_rules": ["pull_request"],
                    "required_approving_review_count": 0,
                    "require_thread_resolution": True,
                    "required_merge_methods": ["squash"],
                    "required_status_checks": [],
                },
            }
            for repository in repos
        ],
    })


def test_auxiliary_registries_accept_canonical_repository_and_project_mapping(tmp_path):
    valid_registries(tmp_path)
    assert validate_auxiliary_registries(tmp_path) == []


def test_auxiliary_registries_reject_source_sink_overlap(tmp_path):
    valid_registries(tmp_path)
    path = tmp_path / "registry/peos/review-sources.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["repositories"].append({
        "repository": "waelhe/Engineering-System",
        "project_id": "egm-engineering-system",
        "default_branch": "main",
        "enabled": True,
        "since_days": 7,
        "max_prs": 10,
    })
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert any("sink repository cannot be a source" in error for error in validate_auxiliary_registries(tmp_path))


def test_auxiliary_registries_reject_secret_fields(tmp_path):
    valid_registries(tmp_path)
    path = tmp_path / "registry/peos/review-sources.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["private_key"] = "do-not-store"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert any("secret-bearing field is forbidden" in error for error in validate_auxiliary_registries(tmp_path))


def test_auxiliary_registries_preserve_mobile_privacy_and_plan_limit_evidence(tmp_path):
    valid_registries(tmp_path)
    path = tmp_path / "registry/peos/repository-governance.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mobile = next(item for item in payload["repositories"] if item["repository"] == "waelhe/mobile-marketplace")
    mobile["visibility"] = "public"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert any("mobile-marketplace must remain private" in error for error in validate_auxiliary_registries(tmp_path))
