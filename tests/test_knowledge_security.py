import json

import pytest

from tools import egm_knowledge
from tools.egm_knowledge import KnowledgeError, redact_excerpt


def test_private_key_crossing_excerpt_boundary_is_redacted_before_truncation():
    private_key = (
        "-----BEGIN PRIVATE KEY-----\n"
        + ("SENSITIVE-PRIVATE-MATERIAL-" * 80)
        + "\n-----END PRIVATE KEY-----"
    )
    # Place the key's BEGIN marker before the 1,200-character boundary and
    # its END marker after it; truncation-first redaction would leak its prefix.
    body = ("ordinary text " * 80) + private_key

    excerpt = redact_excerpt(body, maximum=1200)

    assert "BEGIN PRIVATE KEY" not in excerpt
    assert "END PRIVATE KEY" not in excerpt
    assert "SENSITIVE-PRIVATE-MATERIAL" not in excerpt
    assert "[REDACTED_PRIVATE_KEY]" in excerpt


def test_json_and_serialized_review_credentials_are_redacted():
    raw_json = (
        '{"password": "example-password-12345", '
        '"client_secret": "example-client-secret-67890", '
        '"access_token": "example-access-token-98765"}'
    )
    serialized_review = json.dumps({"review": {"body": raw_json}})

    for body in (raw_json, serialized_review):
        excerpt = redact_excerpt(body)
        assert "example-password-12345" not in excerpt
        assert "example-client-secret-67890" not in excerpt
        assert "example-access-token-98765" not in excerpt
        assert "[REDACTED]" in excerpt


def test_write_index_rejects_symlinked_destination_without_touching_external_file(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    knowledge_dir = root / "knowledge"
    knowledge_dir.mkdir(parents=True)
    external = tmp_path / "external-index.json"
    external.write_text("keep-this-content", encoding="utf-8")
    (knowledge_dir / "index.json").symlink_to(external)

    monkeypatch.setattr(egm_knowledge, "ROOT", root)
    monkeypatch.setattr(egm_knowledge, "KNOWLEDGE", knowledge_dir)

    with pytest.raises(KnowledgeError, match="symbolic links are not allowed"):
        egm_knowledge.write_index()

    assert external.read_text(encoding="utf-8") == "keep-this-content"


def test_receive_signal_rejects_symlinked_inbox_without_writing_outside_repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    knowledge_dir = root / "knowledge"
    knowledge_dir.mkdir(parents=True)
    external = tmp_path / "external-inbox"
    external.mkdir()
    (knowledge_dir / "inbox").symlink_to(external, target_is_directory=True)

    monkeypatch.setattr(egm_knowledge, "ROOT", root)
    monkeypatch.setattr(egm_knowledge, "KNOWLEDGE", knowledge_dir)
    monkeypatch.setattr(egm_knowledge, "registered_project_ids", lambda: {"sample-project"})

    payload = {
        "project_id": "sample-project",
        "provider": "github",
        "source_id": "review-123",
        "source_url": "https://github.com/owner/repo/pull/1",
        "title": "Review signal",
        "body": "A review body without credentials.",
        "repository": "owner/repo",
        "source_kind": "github_review",
    }

    with pytest.raises(KnowledgeError, match="symbolic links are not allowed"):
        egm_knowledge.receive_signal(payload)

    assert list(external.iterdir()) == []

