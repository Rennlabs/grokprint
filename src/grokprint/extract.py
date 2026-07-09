"""Deterministic turn extract — HAPPENED floor + heuristic NEED/ATTENTION.

Primary source: events.jsonl (turn_started … turn_ended, tool_*).
Secondary: chat_history.jsonl last assistant message for NEED heuristics.
Optional: updates.jsonl tool titles (bounded tail read).
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .redaction import redact_card
from .session import card_paths, find_session_dir, project_last_print_path, read_summary

SCHEMA_VERSION = 1

# Parent-only policy: skip writing digests for known subagent relationships.
SUBAGENT_RELATIONSHIPS = frozenset({"subagent", "child", "fork_child"})

NEED_PATTERNS = [
    re.compile(r"\?\s*$"),
    re.compile(r"(?i)\b(do you want|should i|shall i|please confirm|confirm that|which (option|one)|pick one|approve|go ahead|reply with|let me know|your call|need you to|what would you like)\b"),
    re.compile(r"(?i)\b(choose|select)\b.{0,40}\b(option|approach|path)\b"),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _last_turn_events(events_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return (events_in_last_turn, turn_started_event).

    Walks the whole events file once, keeping only the current turn buffer.
    phase_changed events are discarded to keep memory small.
    """
    turn: list[dict[str, Any]] = []
    started: dict[str, Any] | None = None
    current: list[dict[str, Any]] = []
    current_started: dict[str, Any] | None = None

    for ev in _iter_jsonl(events_path):
        t = ev.get("type")
        if t == "phase_changed":
            continue
        if t == "turn_started":
            current = [ev]
            current_started = ev
            continue
        if current_started is not None:
            current.append(ev)
            if t == "turn_ended":
                turn = current
                started = current_started
                current = []
                current_started = None

    # In-progress turn (Stop fired before turn_ended flushed)
    if current_started is not None and current:
        turn = current
        started = current_started

    return turn, started


def _aggregate_tools(turn: list[dict[str, Any]]) -> tuple[list[str], list[str], Counter[str]]:
    """Return (happened_lines, attention_lines, outcome_counter)."""
    started: Counter[str] = Counter()
    completed: Counter[tuple[str, str]] = Counter()
    denials: list[str] = []
    outcomes: Counter[str] = Counter()

    for ev in turn:
        t = ev.get("type")
        name = str(ev.get("tool_name") or "tool")
        if t == "tool_started":
            started[name] += 1
        elif t == "tool_completed":
            outcome = str(ev.get("outcome") or "unknown")
            completed[(name, outcome)] += 1
            outcomes[outcome] += 1
        elif t == "permission_resolved":
            decision = str(ev.get("decision") or "")
            if decision and decision.lower() not in ("allow", "allowed", "approved"):
                denials.append(f"permission {decision}: {name}")

    happened: list[str] = []
    attention: list[str] = []

    # Prefer completed tallies; fall back to started if completions missing.
    if completed:
        # Group by tool for compact display
        by_tool: dict[str, Counter[str]] = {}
        for (name, outcome), n in completed.items():
            by_tool.setdefault(name, Counter())[outcome] += n
        # Sort by total desc
        items = sorted(by_tool.items(), key=lambda kv: sum(kv[1].values()), reverse=True)
        total = sum(sum(c.values()) for _, c in items)
        if total <= 8:
            for name, oc in items:
                parts = [f"{o}×{n}" if n > 1 else o for o, n in oc.items()]
                line = f"{name} → {', '.join(parts)}"
                happened.append(line)
                if any(o not in ("success", "ok", "completed") for o in oc):
                    attention.append(line)
        else:
            top = items[:6]
            summary_bits = []
            for name, oc in top:
                n = sum(oc.values())
                bad = sum(v for k, v in oc.items() if k not in ("success", "ok", "completed"))
                if bad:
                    summary_bits.append(f"{name}×{n} ({bad} fail)")
                    attention.append(f"{name}: {bad} non-success")
                else:
                    summary_bits.append(f"{name}×{n}")
            extra = len(items) - len(top)
            line = f"{total} tools: " + ", ".join(summary_bits)
            if extra > 0:
                line += f" +{extra} more"
            happened.append(line)
    elif started:
        bits = [f"{n}×{c}" if c > 1 else n for n, c in started.most_common(8)]
        happened.append("tools started (no completion yet): " + ", ".join(bits))
        attention.append("turn may still be in progress — tool completions missing")

    for d in denials[:5]:
        attention.append(d)

    return happened, attention, outcomes


def _tail_assistant_text(chat_path: Path, max_chars: int = 4000) -> str:
    if not chat_path.exists():
        return ""
    last_assistant = ""
    # Forward scan keeping last assistant — chat_history is usually small.
    for obj in _iter_jsonl(chat_path):
        role = obj.get("type") or obj.get("role")
        if role not in ("assistant", "model"):
            continue
        content = obj.get("content")
        if isinstance(content, str):
            last_assistant = content
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") in (None, "text"):
                    parts.append(str(block.get("text") or ""))
                elif isinstance(block, str):
                    parts.append(block)
            last_assistant = "".join(parts)
        elif isinstance(content, dict):
            last_assistant = str(content.get("text") or "")
    return last_assistant[-max_chars:]


def _extract_need(text: str, limit: int = 6) -> list[str]:
    if not text:
        return []
    needs: list[str] = []
    seen: set[str] = set()
    # Prefer line-level questions
    for raw in text.splitlines():
        line = raw.strip().lstrip("#*- ").strip()
        if not line or len(line) < 8:
            continue
        if any(p.search(line) for p in NEED_PATTERNS):
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            needs.append(line[:240])
            if len(needs) >= limit:
                return needs
    # Fallback: last paragraph with a question mark
    if not needs and "?" in text:
        for para in reversed(re.split(r"\n\s*\n", text)):
            para = para.strip()
            if "?" in para:
                # Take first sentence with ?
                for sent in re.split(r"(?<=[?])\s+", para):
                    if "?" in sent:
                        needs.append(sent.strip()[:240])
                        break
                break
    return needs[:limit]


def _extract_next(text: str) -> str | None:
    if not text:
        return None
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if low.startswith(("next:", "next step:", "**next", "recommended next")):
            cleaned = re.sub(r"^[\*\s]*next(?:\s*step)?\s*:\s*", "", line, flags=re.I)
            cleaned = cleaned.strip("* ").strip()
            return cleaned[:200] if cleaned else None
    return None


def _status_from_turn(turn: list[dict[str, Any]], started: dict[str, Any] | None) -> str:
    for ev in reversed(turn):
        if ev.get("type") == "turn_ended":
            outcome = str(ev.get("outcome") or "completed").lower()
            if outcome in ("completed", "success", "endturn", "end_turn"):
                return "completed"
            if outcome in ("cancelled", "canceled", "aborted", "interrupted"):
                return "cancelled"
            if outcome in ("error", "failed", "failure"):
                return "error"
            return outcome if outcome in ("completed", "cancelled", "error", "missing", "in_progress") else "completed"
    if started is not None:
        return "in_progress"
    return "missing"


def extract_card(
    session_dir: Path | None = None,
    session_id: str | None = None,
    cwd: str | Path | None = None,
    *,
    parent_only: bool = True,
    include_chat: bool = True,
) -> dict[str, Any]:
    """Build a Grokprint card for the latest turn in a session."""
    t0 = time.perf_counter()
    sdir = session_dir or find_session_dir(session_id=session_id, cwd=cwd)

    if sdir is None:
        return redact_card(
            {
                "version": SCHEMA_VERSION,
                "session_id": session_id or os.environ.get("GROK_SESSION_ID") or "unknown",
                "turn_number": None,
                "status": "missing",
                "ts": _utc_now(),
                "happened": ["session directory not found"],
                "attention": ["could not locate events.jsonl — check GROK_SESSION_ID / cwd"],
                "need_from_you": [],
                "next": None,
                "sources": {"events": False, "chat_history": False, "updates": False, "model": False},
                "redacted": True,
                "stale": True,
                "parent_only": parent_only,
                "model_id": None,
                "extract_ms": round((time.perf_counter() - t0) * 1000, 2),
                "session_dir": None,
            }
        )

    summary = read_summary(sdir)
    sid = summary.get("info", {}).get("id") or sdir.name

    events_path = sdir / "events.jsonl"
    turn, started = _last_turn_events(events_path)

    relationship = (started or {}).get("session_relationship") or "primary"
    if parent_only and str(relationship).lower() in SUBAGENT_RELATIONSHIPS:
        return redact_card(
            {
                "version": SCHEMA_VERSION,
                "session_id": sid,
                "turn_number": (started or {}).get("turn_number"),
                "status": "missing",
                "ts": _utc_now(),
                "happened": [f"subagent turn skipped (parent_only policy; relationship={relationship})"],
                "attention": [],
                "need_from_you": [],
                "next": None,
                "sources": {"events": True, "chat_history": False, "updates": False, "model": False},
                "redacted": True,
                "stale": False,
                "parent_only": True,
                "model_id": (started or {}).get("model_id") or summary.get("current_model_id"),
                "extract_ms": round((time.perf_counter() - t0) * 1000, 2),
                "session_dir": str(sdir),
            }
        )

    happened, attention, outcomes = _aggregate_tools(turn)
    status = _status_from_turn(turn, started)

    if not turn:
        happened = ["no turn events found"]
        attention = ["events.jsonl empty or missing turn_started"]
        status = "missing"

    if status == "cancelled":
        attention = [f"turn {status}"] + attention
    elif status == "error":
        attention = ["turn ended with error"] + attention
    elif status == "in_progress":
        attention = ["turn still in progress at extract time"] + attention

    if outcomes.get("error") or outcomes.get("failure") or outcomes.get("failed"):
        bad = outcomes.get("error", 0) + outcomes.get("failure", 0) + outcomes.get("failed", 0)
        if not any("fail" in a.lower() or "error" in a.lower() for a in attention):
            attention.insert(0, f"{bad} tool error(s)")

    need: list[str] = []
    next_line: str | None = None
    used_chat = False
    if include_chat:
        text = _tail_assistant_text(sdir / "chat_history.jsonl")
        if text:
            used_chat = True
            need = _extract_need(text)
            next_line = _extract_next(text)

    if not happened:
        happened = ["no tools in last turn"]

    # Cap lists to schema limits
    happened = happened[:12]
    attention = attention[:8]
    need = need[:6]

    card = {
        "version": SCHEMA_VERSION,
        "session_id": sid,
        "turn_number": (started or {}).get("turn_number"),
        "status": status,
        "ts": _utc_now(),
        "happened": happened,
        "attention": attention,
        "need_from_you": need,
        "next": next_line,
        "sources": {
            "events": bool(turn),
            "chat_history": used_chat,
            "updates": False,
            "model": False,
        },
        "redacted": False,
        "stale": status == "missing",
        "parent_only": parent_only,
        "model_id": (started or {}).get("model_id") or summary.get("current_model_id"),
        "extract_ms": round((time.perf_counter() - t0) * 1000, 2),
        "session_dir": str(sdir),
    }
    return redact_card(card)


def write_card(
    card: dict[str, Any],
    session_dir: Path | None = None,
    *,
    also_project: bool = True,
    cwd: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write grokprint.json + last-print.md. Returns (json_path, md_path)."""
    from .render import render_markdown

    sdir = session_dir
    if sdir is None and card.get("session_dir"):
        sdir = Path(str(card["session_dir"]))
    if sdir is None:
        sdir = find_session_dir(session_id=card.get("session_id"), cwd=cwd)
    if sdir is None:
        # Fall back to workspace .grokprint/
        root = Path(cwd or os.environ.get("GROK_WORKSPACE_ROOT") or os.getcwd())
        sdir = root / ".grokprint"
    sdir.mkdir(parents=True, exist_ok=True)

    json_path, md_path = card_paths(sdir)
    # If card_paths points into a real session, use it; else write under sdir
    if not (sdir / "events.jsonl").exists() and sdir.name == ".grokprint":
        json_path = sdir / "grokprint.json"
        md_path = sdir / "last-print.md"

    payload = redact_card(card)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    if also_project:
        proj = project_last_print_path(cwd)
        try:
            proj.parent.mkdir(parents=True, exist_ok=True)
            proj.write_text(render_markdown(payload), encoding="utf-8")
            (proj.parent / "grokprint.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        except OSError:
            pass

    return json_path, md_path


def extract_and_write(
    session_id: str | None = None,
    cwd: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    card = extract_card(session_id=session_id, cwd=cwd, **kwargs)
    write_card(card, cwd=cwd)
    return card
