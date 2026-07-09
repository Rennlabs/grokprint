import json
from pathlib import Path

from grokprint.loop import detect_loop_modes, should_write_this_stop


def test_detect_active_ralph(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = tmp_path / ".omc" / "state"
    state.mkdir(parents=True)
    (state / "ralph-state.json").write_text(
        json.dumps({"active": True, "_meta": {"mode": "ralph"}}),
        encoding="utf-8",
    )
    modes = detect_loop_modes(cwd=tmp_path)
    assert modes == ["ralph"]


def test_inactive_ignored(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = tmp_path / ".omc" / "state"
    state.mkdir(parents=True)
    (state / "ralph-state.json").write_text(
        json.dumps({"active": False, "_meta": {"mode": "ralph"}}),
        encoding="utf-8",
    )
    assert detect_loop_modes(cwd=tmp_path) == []


def test_throttle_every_n(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROKPRINT_LOOP_EVERY", "3")
    modes = ["ultrawork"]
    results = [should_write_this_stop(tmp_path, modes)[0] for _ in range(6)]
    # writes on 3rd and 6th
    assert results == [False, False, True, False, False, True]


def test_no_throttle_without_loop(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROKPRINT_LOOP_EVERY", "5")
    assert should_write_this_stop(tmp_path, [])[0] is True
