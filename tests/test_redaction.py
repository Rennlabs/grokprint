from grokprint.redaction import looks_like_secret, redact_card, redact_text

# Build fake token shapes from pieces so the source file is leak-scan clean.
_FAKE_GHP = "ghp_" + ("a" * 36)
_FAKE_SK = "sk-" + ("b" * 32)


def test_redacts_github_token():
    s = f"token {_FAKE_GHP}"
    out = redact_text(s)
    assert "ghp_" not in out
    assert "REDACTED" in out


def test_redacts_sk_key():
    s = f"use {_FAKE_SK} now"
    assert "sk-b" not in redact_text(s)
    assert "REDACTED" in redact_text(s)


def test_redacts_env_assignment():
    s = "export OPENAI_API_KEY=supersecretvalue123"
    out = redact_text(s)
    assert "supersecretvalue123" not in out
    assert "REDACTED" in out


def test_redact_card_flags():
    card = {
        "happened": ["ok"],
        "attention": [f"token {_FAKE_GHP}"],
        "need_from_you": ["Should I rotate?"],
        "next": None,
        "redacted": False,
    }
    out = redact_card(card)
    assert out["redacted"] is True
    assert "ghp_" not in out["attention"][0]


def test_looks_like_secret():
    assert looks_like_secret(_FAKE_GHP)
    assert not looks_like_secret("plain status line")


def test_redacts_slack_and_db_url():
    slack = "xoxb-" + ("9" * 24)
    assert "xoxb-" not in redact_text(f"token {slack}")
    out = redact_text("postgres://alice:s3cret@db.example/app")
    assert "s3cret" not in out
    assert "REDACTED" in out
