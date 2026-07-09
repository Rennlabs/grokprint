#!/usr/bin/env python3
"""Grok Stop hook: write grokprint card for the completed turn.

Passive hook — exit 0 always (fail-open). Stdout ignored for control flow.
Set GROKPRINT_ANNOTATE=1 to print compact card to stdout (scrollback annotation).
Set GROKPRINT_DISABLE=1 to no-op.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Resolve package from repo layout: hooks/ -> repo root -> src/
_HOOK_DIR = Path(__file__).resolve().parent
_REPO = _HOOK_DIR.parent
_SRC = _REPO / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Also allow installed path via GROKPRINT_ROOT
_root = os.environ.get("GROKPRINT_ROOT")
if _root:
    p = Path(_root) / "src"
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _read_stdin() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def main() -> int:
    if os.environ.get("GROKPRINT_DISABLE", "").strip() in ("1", "true", "yes", "on"):
        return 0

    payload = _read_stdin()
    session_id = (
        os.environ.get("GROK_SESSION_ID")
        or payload.get("sessionId")
        or payload.get("session_id")
        or ""
    )
    cwd = (
        os.environ.get("GROK_WORKSPACE_ROOT")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or payload.get("workspaceRoot")
        or payload.get("cwd")
        or os.getcwd()
    )

    try:
        from grokprint.extract import extract_and_write
        from grokprint.render import render_compact

        card = extract_and_write(session_id=session_id or None, cwd=cwd)
        if os.environ.get("GROKPRINT_ANNOTATE", "").strip() in ("1", "true", "yes", "on"):
            # Appears as hook annotation in scrollback when plugins UI enabled
            sys.stdout.write(render_compact(card) + "\n")
    except Exception as exc:
        # Fail-open: never break the agent turn
        if os.environ.get("GROKPRINT_DEBUG"):
            sys.stderr.write(f"grokprint stop_print error: {exc}\n")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
