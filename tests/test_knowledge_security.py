from tools.egm_knowledge import redact_excerpt


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
