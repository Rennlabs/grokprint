from grokprint.redaction import looks_like_secret, redact_card, redact_text


def test_redacts_github_token():
    s = "token ghp_abcdefghijklmnopqrstuvwxyz012345"
    out = redact_text(s)
    assert "ghp_" not in out
    assert "REDACTED" in out


def test_redacts_sk_key():
    s = "use sk-abcdefghijklmnopqrstuvwxyz012345 now"
    assert "sk-abc" not in redact_text(s)


def test_redacts_env_assignment():
    s = "export OPENAI_API_KEY=supersecretvalue123"
    out = redact_text(s)
    assert "supersecretvalue123" not in out
    assert "REDACTED" in out


def test_redact_card_flags():
    card = {
        "happened": ["ok"],
        "attention": ["token ghp_abcdefghijklmnopqrstuvwxyz012345"],
        "need_from_you": ["Should I rotate?"],
        "next": None,
        "redacted": False,
    }
    out = redact_card(card)
    assert out["redacted"] is True
    assert "ghp_" not in out["attention"][0]


def test_looks_like_secret():
    assert looks_like_secret("ghp_abcdefghijklmnopqrstuvwxyz012345")
    assert not looks_like_secret("plain status line")
