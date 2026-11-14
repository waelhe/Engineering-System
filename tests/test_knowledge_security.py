from tools.egm_knowledge import redact_excerpt


def test_private_key_is_redacted_before_excerpt_truncation():
    private_key = (
        "-----BEGIN PRIVATE KEY-----\n"
        + ("SENSITIVE-PRIVATE-MATERIAL-" * 80)
        + "\n-----END PRIVATE KEY-----"
    )
    body = ("ordinary text " * 90) + private_key

    excerpt = redact_excerpt(body, maximum=1200)

    assert "BEGIN PRIVATE KEY" not in excerpt
    assert "END PRIVATE KEY" not in excerpt
    assert "SENSITIVE-PRIVATE-MATERIAL" not in excerpt
    assert "[REDACTED_PRIVATE_KEY]" in excerpt
