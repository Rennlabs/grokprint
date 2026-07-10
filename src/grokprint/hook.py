"""Stop-hook entrypoint: ``python3 -m grokprint.hook``

Path-resilient: works after ``pip install -e .`` without depending on
absolute paths baked into hook JSON.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    if os.environ.get("GROKPRINT_DISABLE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return 0

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

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
        if os.environ.get("GROKPRINT_ANNOTATE", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            sys.stdout.write(render_compact(card) + "\n")
    except Exception as exc:
        if os.environ.get("GROKPRINT_DEBUG"):
            sys.stderr.write(f"grokprint hook error: {exc}\n")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
