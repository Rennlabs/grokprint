"""Optional live-session p95 latency check.

Skipped unless GROKPRINT_LIVE=1 and real sessions exist.
"""

from __future__ import annotations

import os
import statistics
import time
from pathlib import Path

import pytest

from grokprint.extract import extract_card
from grokprint.session import grok_home


@pytest.mark.skipif(os.environ.get("GROKPRINT_LIVE") != "1", reason="Set GROKPRINT_LIVE=1 to run")
def test_live_session_extract_p95():
    sessions = grok_home() / "sessions"
    if not sessions.is_dir():
        pytest.skip("no sessions dir")

    candidates: list[Path] = []
    for group in sessions.iterdir():
        if not group.is_dir():
            continue
        for sdir in group.iterdir():
            events = sdir / "events.jsonl"
            if events.is_file() and events.stat().st_size > 50_000:
                candidates.append(sdir)
    candidates.sort(key=lambda p: (p / "events.jsonl").stat().st_size, reverse=True)
    candidates = candidates[:15]
    if not candidates:
        pytest.skip("no large sessions")

    times = []
    for sdir in candidates:
        t0 = time.perf_counter()
        card = extract_card(session_dir=sdir)
        times.append((time.perf_counter() - t0) * 1000)
        assert "happened" in card

    times_sorted = sorted(times)
    p95 = times_sorted[max(0, int(len(times_sorted) * 0.95) - 1)]
    median = statistics.median(times)
    print(f"\nlive extract n={len(times)} median={median:.1f}ms p95={p95:.1f}ms max={max(times):.1f}ms")
    assert p95 < 2000, f"p95 {p95:.1f}ms exceeds 2000ms budget"
