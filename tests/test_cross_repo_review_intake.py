from __future__ import annotations

import json

import pytest

import tools.cross_repo_review_intake as intake
from tools import github_review_intake as local_intake


def registry(repositories=None):
    return {
        "schema_version": 1,
        "sink_repository": "waelhe/Engineering-System",
        "repositories": repositories if repositories is not None else [
            {
                "repository": "waelhe/app-java-v3",
                "project_id": "app-java-v3",
                "default_branch": "main",
                "enabled": True,
                "since_days": 7,
                "max_prs": 50,
            }
        ],
    }


def write_registry(tmp_path, value):
    path = tmp_path / "review-sources.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_load_registry_accepts_scoped_source_and_sink(tmp_path):
    loaded = intake.load_registry(write_registry(tmp_path, registry()))
    assert loaded["sink_repository"] == "waelhe/Engineering-System"
    assert loaded["repositories"] == registry()["repositories"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda data: data.update({"sink_repository": "not-a-repository"}), "sink_repository"),
        (lambda data: data["repositories"][0].update({"repository": "waelhe/Engineering-System"}), "must not also"),
        (lambda data: data["repositories"][0].update({"project_id": "../escape"}), "project_id is invalid"),
        (lambda data: data["repositories"][0].update({"max_prs": 101}), "max_prs must be 1..100"),
        (lambda data: data["repositories"][0].update({"since_days": 0}), "since_days must be 1..90"),
        (lambda data: data["repositories"][0].update({"enabled": "true"}), "enabled must be boolean"),
    ],
)
def test_load_registry_rejects_invalid_or_unsafe_source_configuration(tmp_path, mutate, message):
    value = registry()
    mutate(value)
    with pytest.raises(intake.IntakeError, match=message):
        intake.load_registry(write_registry(tmp_path, value))


def test_load_registry_rejects_duplicate_source_repository_and_project(tmp_path):
    sources = registry()["repositories"]
    duplicate_repo = sources + [{**sources[0], "project_id": "another-project"}]
    with pytest.raises(intake.IntakeError, match="Duplicate source repository"):
        intake.load_registry(write_registry(tmp_path, registry(duplicate_repo)))

    duplicate_project = sources + [{**sources[0], "repository": "waelhe/another-repo"}]
    with pytest.raises(intake.IntakeError, match="Duplicate source project_id"):
        intake.load_registry(write_registry(tmp_path, registry(duplicate_project)))


def test_collect_source_repository_scans_only_prs_targeting_registered_default_branch(monkeypatch):
    api_calls = []
    collected = []

    def fake_api(method, path, token, payload=None):
        api_calls.append((method, path, token))
        if path == "/repos/waelhe/app-java-v3":
            return {"default_branch": "main"}
        if path.endswith("/pulls/10"):
            return {"base": {"ref": "main", "repo": {"full_name": "waelhe/app-java-v3"}}}
        if path.endswith("/pulls/11"):
            return {"base": {"ref": "release/next", "repo": {"full_name": "waelhe/app-java-v3"}}}
        raise AssertionError(path)

    def fake_recent(repository, token, since_days, maximum):
        assert repository == "waelhe/app-java-v3"
        assert token == "source-read-only-token"
        assert since_days == 7 and maximum == 50
        return [10, 11]

    def fake_collect(repository, project_id, token, number, event_action):
        collected.append((repository, project_id, token, number, event_action))
        return {"created": 2, "duplicate": 1, "objects": 3}

    monkeypatch.setattr(intake, "api_request", fake_api)
    monkeypatch.setattr(intake, "recent_open_prs", fake_recent)
    monkeypatch.setattr(intake, "collect_one_pr", fake_collect)

    result = intake.collect_source_repository(
        registry()["repositories"][0],
        "source-read-only-token",
        "scheduled_cross_repository_scan",
    )

    assert result["selected_prs"] == [10]
    assert result["skipped_non_default_base_prs"] == [11]
    assert result["created"] == 2 and result["duplicate"] == 1 and result["objects"] == 3
    assert collected == [
        ("waelhe/app-java-v3", "app-java-v3", "source-read-only-token", 10,
         "scheduled_cross_repository_scan")
    ]
    assert all(call[2] == "source-read-only-token" for call in api_calls)


def test_source_default_branch_drift_fails_closed(monkeypatch):
    monkeypatch.setattr(
        intake,
        "api_request",
        lambda *args, **kwargs: {"default_branch": "trunk"},
    )
    with pytest.raises(intake.IntakeError, match="does not match GitHub's current default branch"):
        intake.collect_source_repository(
            registry()["repositories"][0],
            "source-read-only-token",
            "workflow_dispatch_cross_repository_scan",
        )


def test_child_process_environment_drops_both_source_and_sink_tokens(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "sink-token")
    monkeypatch.setenv("EGM_SOURCE_GITHUB_TOKEN", "source-token")
    monkeypatch.setenv("EGM_SINK_GITHUB_TOKEN", "extra-sink-token")

    environment = local_intake.unprivileged_child_environment()

    assert "GITHUB_TOKEN" not in environment
    assert "EGM_SOURCE_GITHUB_TOKEN" not in environment
    assert "EGM_SINK_GITHUB_TOKEN" not in environment
