"""Locate Grok session directories and related paths."""

from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path
from typing import Any


def grok_home() -> Path:
    return Path(os.environ.get("GROK_HOME") or Path.home() / ".grok")


def encode_cwd(cwd: str | Path) -> str:
    # Grok URL-encodes the working directory; keeps path separators as %2F.
    abs_cwd = str(Path(cwd).resolve())
    return urllib.parse.quote(abs_cwd, safe="")


def session_group_dir(cwd: str | Path | None = None) -> Path:
    root = cwd or os.environ.get("GROK_WORKSPACE_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return grok_home() / "sessions" / encode_cwd(root)


def find_session_dir(
    session_id: str | None = None,
    cwd: str | Path | None = None,
) -> Path | None:
    """Resolve session directory.

    Preference order:
    1. Explicit session_id under cwd group
    2. GROK_SESSION_ID under cwd group
    3. Search all session groups for the id
    4. Most recently updated session under cwd group
    """
    sid = session_id or os.environ.get("GROK_SESSION_ID") or ""
    group = session_group_dir(cwd)

    if sid:
        candidate = group / sid
        if candidate.is_dir() and (candidate / "events.jsonl").exists():
            return candidate
        # Fall back: scan all groups (subagent / path encoding edge cases)
        sessions_root = grok_home() / "sessions"
        if sessions_root.is_dir():
            for child in sessions_root.iterdir():
                if not child.is_dir():
                    continue
                hit = child / sid
                if hit.is_dir() and (hit / "events.jsonl").exists():
                    return hit

    if group.is_dir():
        newest: Path | None = None
        newest_mtime = -1.0
        for child in group.iterdir():
            if not child.is_dir():
                continue
            events = child / "events.jsonl"
            if not events.exists():
                continue
            m = events.stat().st_mtime
            if m > newest_mtime:
                newest_mtime = m
                newest = child
        return newest

    return None


def read_summary(session_dir: Path) -> dict[str, Any]:
    path = session_dir / "summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def card_paths(session_dir: Path) -> tuple[Path, Path]:
    """Return (json_path, markdown_path) for the digest."""
    return session_dir / "grokprint.json", session_dir / "last-print.md"


def project_last_print_path(cwd: str | Path | None = None) -> Path:
    """Workspace-local symlink/copy target for quick access."""
    root = Path(cwd or os.environ.get("GROK_WORKSPACE_ROOT") or os.getcwd())
    return root / ".grokprint" / "last-print.md"
