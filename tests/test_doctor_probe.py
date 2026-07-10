from pathlib import Path

from grokprint.cli import _events_compat_probe


def test_compat_probe_on_fixture(tmp_path: Path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                '{"type":"turn_started","schema_version":"1.0","turn_number":0}',
                '{"type":"tool_completed","tool_name":"read_file","outcome":"success"}',
                '{"type":"turn_ended","outcome":"completed"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    c = _events_compat_probe(events)
    assert c["ok"] is True
    assert any("1.0" in s for s in c["schema_versions"])


def test_compat_probe_missing(tmp_path: Path):
    c = _events_compat_probe(tmp_path / "nope.jsonl")
    assert c["ok"] is False
