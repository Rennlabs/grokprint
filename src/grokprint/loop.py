"""Read-only detection of active harness/loop modes (.omc state).

Grokprint never controls loops — it only labels the card so humans know
the Stop was mid-ralph/ultrawork/etc.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

# Align with loop-verifier-gate / loop-discipline-reminder.
LOOP_MODES = frozenset(
    {
        "ralph",
        "ultrawork",
        "autopilot",
        "autoresearch",
        "ultraqa",
        "self-improve",
        "ralplan",
        "team",
        "omc-teams",
        "ultragoal",
        "ceo",
        "eskill-sprint",
        "eskill-overnight",
        "looptimal",
        "fablefuse",
        "fleet-fuse",
    }
)

FRESH_MS = 24 * 60 * 60 * 1000


def _mode_from_file(name: str, data: dict[str, Any]) -> str:
    meta = data.get("_meta") if isinstance(data.get("_meta"), dict) else {}
    m = meta.get("mode") or data.get("mode")
    if m:
        return str(m)
    if name.endswith("-state.json"):
        return name[: -len("-state.json")]
    return name


def _state_dirs(cwd: str | Path | None, session_id: str | None) -> list[Path]:
    root = Path(cwd or os.environ.get("GROK_WORKSPACE_ROOT") or os.getcwd())
    base = root / ".omc" / "state"
    dirs = [base]
    sid = session_id or os.environ.get("GROK_SESSION_ID")
    if sid:
        dirs.append(base / "sessions" / str(sid))
    return dirs


def detect_loop_modes(
    cwd: str | Path | None = None,
    session_id: str | None = None,
    *,
    now_ms: float | None = None,
) -> list[str]:
    """Return sorted active loop mode names (may be empty)."""
    now = now_ms if now_ms is not None else time.time() * 1000
    found: set[str] = set()
    for d in _state_dirs(cwd, session_id):
        if not d.is_dir():
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            if not name.endswith("-state.json"):
                continue
            path = d / name
            try:
                st = path.stat()
                if now - (st.st_mtime * 1000) > FRESH_MS:
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            if not isinstance(data, dict) or data.get("active") is not True:
                continue
            mode = _mode_from_file(name, data)
            if mode in LOOP_MODES:
                found.add(mode)
    return sorted(found)


def should_write_this_stop(
    session_dir: Path | None,
    loop_modes: list[str],
) -> tuple[bool, str | None]:
    """Throttle file writes during hot loops.

    GROKPRINT_LOOP_EVERY=N — while loop_active, write only every Nth Stop
    (default 1 = always). Counter stored in session_dir/.grokprint-loop-count.
    """
    if not loop_modes:
        return True, None
    raw = (os.environ.get("GROKPRINT_LOOP_EVERY") or "1").strip()
    try:
        every = max(1, int(raw))
    except ValueError:
        every = 1
    if every <= 1 or session_dir is None:
        return True, None

    counter_path = session_dir / ".grokprint-loop-count"
    try:
        n = int(counter_path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        n = 0
    n += 1
    try:
        counter_path.write_text(str(n) + "\n", encoding="utf-8")
    except OSError:
        return True, None
    if n % every == 0:
        return True, None
    return False, f"throttled loop Stop {n} (every {every})"
