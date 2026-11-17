import hashlib
import json

import pytest

import tools.validate_intake_pr as intake_validation

from tools.validate_intake_pr import (
    IntakeValidationError,
    parse_name_status_z,
    validate_blob_modes,
    validate_change_set,
    validate_signal_record,
)


def sample_signal():
    provider = "github"
    repository = "owner/repo"
    source_id = "github_review-101"
    source_identity = f"{provider}:{repository}:{source_id}"
    digest = hashlib.sha256(b"source body").hexdigest()
    signal_id = "sig-" + hashlib.sha256(
        (source_identity + ":" + digest).encode("utf-8")
    ).hexdigest()[:24]
    return f"knowledge/inbox/{signal_id}.json", {
        "schema_version": 1,
        "id": signal_id,
        "type": "signal",
        "project_id": "sample-project",
        "title": "Review comment",
        "summary": "Source body",
        "assessment": "observed",
        "lifecycle": "untriaged",
        "approval": "not_required",
        "provider": provider,
        "source_identity": source_identity,
        "source_id": source_id,
        "payload_digest": digest,
        "sources": [{
            "kind": "github_review",
            "uri": "https://github.com/owner/repo/pull/9",
            "repository": repository,
            "source_id": source_id,
            "trust_level": "untrusted_source",
        }],
    }


def test_intake_change_contract_accepts_only_new_signals_and_generated_index():
    path, _ = sample_signal()
    signals, index_path = validate_change_set([
        ("A", path),
        ("M", "knowledge/index.json"),
    ])
    assert signals == [path]
    assert index_path == "knowledge/index.json"


@pytest.mark.parametrize("changes", [
    [("M", "knowledge/inbox/sig-" + "a" * 24 + ".json"), ("M", "knowledge/index.json")],
    [("A", "knowledge/inbox/not-a-signal.json"), ("M", "knowledge/index.json")],
    [("A", "knowledge/inbox/sig-" + "a" * 24 + ".json"), ("A", "src/untrusted.py"), ("M", "knowledge/index.json")],
    [("A", "knowledge/inbox/sig-" + "a" * 24 + ".json"), ("D", "knowledge/index.json")],
    [("A", "knowledge/inbox/sig-" + "a" * 24 + ".json")],
])
def test_intake_change_contract_rejects_mutations_or_code(changes):
    with pytest.raises(IntakeValidationError):
        validate_change_set(changes)


def test_signal_validator_requires_untrusted_snapshot_and_digest_bound_path():
    path, record = sample_signal()
    validate_signal_record(path, json.dumps(record).encode("utf-8"))

    record["approval"] = "approved"
    with pytest.raises(IntakeValidationError, match="promoted state"):
        validate_signal_record(path, json.dumps(record).encode("utf-8"))


def test_signal_validator_rejects_id_mismatch():
    path, record = sample_signal()
    record["payload_digest"] = "0" * 64
    with pytest.raises(IntakeValidationError, match="Signal ID does not match"):
        validate_signal_record(path, json.dumps(record).encode("utf-8"))


def test_name_status_parser_handles_null_delimited_paths():
    assert parse_name_status_z(
        "A\0knowledge/inbox/sig-abc.json\0M\0knowledge/index.json\0"
    ) == [
        ("A", "knowledge/inbox/sig-abc.json"),
        ("M", "knowledge/index.json"),
    ]


def test_intake_tree_rejects_symlink_and_executable_mode(monkeypatch):
    entries = (
        b"120000 blob abc\tknowledge/inbox/sig-x.json\0",
        b"100755 blob abc\tknowledge/inbox/sig-x.json\0",
    )
    for raw in entries:
        monkeypatch.setattr(
            "tools.validate_intake_pr.git",
            lambda *args, raw=raw, **kwargs: raw,
        )
        with pytest.raises(IntakeValidationError):
            validate_blob_modes(
                "refs/remotes/origin/branch",
                ["knowledge/inbox/sig-x.json"],
            )



def test_signal_validator_binds_source_identity_to_repository_provenance():
    path, record = sample_signal()
    record["source_identity"] = "github:another/repository:github_review-101"
    with pytest.raises(IntakeValidationError, match="source identity or body digest"):
        validate_signal_record(path, json.dumps(record).encode("utf-8"))



def test_validate_intake_pr_enforces_append_only_guard_before_materializing_data(monkeypatch):
    signal_path, _ = sample_signal()
    head_sha = "a" * 40
    calls = []

    def fake_git(*args, check=True, binary=False):
        calls.append(args)
        if args[0] == "fetch":
            return b"" if binary else ""
        if args[0] == "rev-parse":
            return head_sha
        if args[0] == "diff":
            return f"A\0{signal_path}\0M\0knowledge/index.json\0"
        raise AssertionError(f"unexpected git command before append-only rejection: {args}")

    monkeypatch.setattr(intake_validation, "git", fake_git)
    monkeypatch.setattr(
        intake_validation,
        "validate_changes",
        lambda base, head: [
            ("M", "knowledge/evidence/history.jsonl",
             "only new files or byte-preserving JSONL appends are allowed")
        ],
    )
    monkeypatch.setattr(
        intake_validation,
        "run_trusted_validation",
        lambda: pytest.fail("trusted validation must not run after append-only rejection"),
    )

    with pytest.raises(IntakeValidationError, match="append-only knowledge guard failed"):
        intake_validation.validate_intake_pr(
            17,
            "main",
            "automation/knowledge-intake-123-1",
            head_sha,
            "main",
            "main",
        )

    assert any(command[0] == "diff" for command in calls)
