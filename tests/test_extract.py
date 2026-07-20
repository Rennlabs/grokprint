from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from grokprint.extract import extract_card, write_card
from grokprint.render import render_compact, render_markdown, render_notification

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str, tmp_path: Path) -> Path:
    src = FIXTURES / name
    dest = tmp_path / name
    shutil.copytree(src, dest)
    # Inject synthetic token shapes at runtime (never store complete
    # ghp_/sk- literals in the repo — keeps leak-scan clean).
    if name == "secrets_turn":
        chat = dest / "chat_history.jsonl"
        if chat.is_file():
            fake_ghp = "ghp_" + ("a" * 36)
            fake_sk = "sk-" + ("b" * 32)
            text = chat.read_text(encoding="utf-8")
            text = text.replace("__FAKE_GHP__", fake_ghp).replace("__FAKE_SK__", fake_sk)
            chat.write_text(text, encoding="utf-8")
    return dest


def test_minimal_turn_extract(tmp_path: Path):
    sdir = _load_fixture("minimal_turn", tmp_path)
    expected = json.loads((sdir / "expected.json").read_text())
    card = extract_card(session_dir=sdir)

    assert card["status"] == expected["status"]
    assert card["turn_number"] == expected["turn_number"]
    assert card["redacted"] is True
    assert card["sources"]["events"] is True
    assert card["sources"]["chat_history"] is True
    assert card["sources"]["updates"] is True
    assert card.get("loop_active") is False
    assert card.get("loop_modes") == []

    joined_h = " ".join(card["happened"]).lower()
    for sub in expected["must_contain_happened_substrings"]:
        assert sub.lower() in joined_h
    # updates title should surface when distinct
    assert "web search" in joined_h or "also:" in joined_h

    joined_a = " ".join(card["attention"]).lower()
    for sub in expected["must_contain_attention_substrings"]:
        assert sub.lower() in joined_a

    joined_n = " ".join(card["need_from_you"]).lower()
    for sub in expected["must_contain_need_substrings"]:
        assert sub.lower() in joined_n

    assert card["extract_ms"] is not None
    assert card["extract_ms"] < 2000


def test_secrets_redacted_from_need(tmp_path: Path):
    sdir = _load_fixture("secrets_turn", tmp_path)
    card = extract_card(session_dir=sdir)
    blob = json.dumps(card)
    assert "ghp_" not in blob
    assert "sk-abc" not in blob
    assert card["need_from_you"], "should still surface the question"
    assert any("rotate" in n.lower() for n in card["need_from_you"])


def test_cancelled_status(tmp_path: Path):
    sdir = _load_fixture("cancelled_turn", tmp_path)
    card = extract_card(session_dir=sdir)
    assert card["status"] == "cancelled"
    assert any("cancel" in a.lower() for a in card["attention"])


def test_write_card(tmp_path: Path):
    sdir = _load_fixture("minimal_turn", tmp_path)
    card = extract_card(session_dir=sdir)
    jpath, mpath = write_card(card, session_dir=sdir, also_project=False)
    assert jpath.exists()
    assert mpath.exists()
    loaded = json.loads(jpath.read_text())
    assert loaded["session_id"] == card["session_id"]
    md = mpath.read_text()
    assert "HAPPENED" in md
    assert "NEED FROM YOU" in md


def test_render_notification_need_first(tmp_path: Path):
    sdir = _load_fixture("minimal_turn", tmp_path)
    card = extract_card(session_dir=sdir)
    body = render_notification(card)
    assert body.startswith("NEED:") or "NEED" in body
    assert len(body) <= 200


def test_render_compact_line_budget(tmp_path: Path):
    sdir = _load_fixture("minimal_turn", tmp_path)
    card = extract_card(session_dir=sdir)
    text = render_compact(card, max_lines=12)
    assert len(text.splitlines()) <= 12


def test_missing_session(tmp_path: Path):
    card = extract_card(session_dir=tmp_path / "does-not-exist")
    # session_dir path that doesn't exist → treat via find or empty events
    # Pass a real empty dir:
    empty = tmp_path / "empty"
    empty.mkdir()
    card = extract_card(session_dir=empty)
    assert card["status"] == "missing"
    assert card["stale"] is True
