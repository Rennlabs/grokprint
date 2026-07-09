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

# Strong decision / action asks (always NEED).
NEED_STRONG = [
    re.compile(
        r"(?i)\b("
        r"do you want|should i|shall i|please confirm|confirm that|"
        r"which (option|one)|pick one|approve|go ahead|reply with|"
        r"let me know|your call|need you to|what would you like|"
        r"want me to|can i (go|proceed|push|merge|deploy)|"
        r"ready for (you|me) to|is it ok (if|to)|are you (ok|fine) with"
        r")\b"
    ),
    re.compile(r"(?i)\b(choose|select)\b.{0,40}\b(option|approach|path)\b"),
    re.compile(r"(?i)\b(postgres|sqlite|mysql|option\s*[abc123])\b.*\?"),
]

# Weak: line ends with ? but may be rhetorical / explanatory.
NEED_WEAK_Q = re.compile(r"\?\s*$")

# Explanatory / rhetorical openers — not user obligations unless strong pattern also hits.
NEED_RHETORICAL = re.compile(
    r"(?i)^(what is|what are|what does|what do|how does|how do|how is|why does|why do|why is|"
    r"when does|where does|who is|note that|for example|e\.g\.|i\.e\.)\b"
)


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


def _strip_fenced_code(text: str) -> str:
    """Remove ``` fenced blocks so code comments don't become NEED."""
    return re.sub(r"```[\s\S]*?```", "\n", text)


def _is_need_line(line: str) -> bool:
    if any(p.search(line) for p in NEED_STRONG):
        return True
    if not NEED_WEAK_Q.search(line):
        return False
    if len(line) > 200:
        return False
    if NEED_RHETORICAL.search(line):
        return False
    # Weak ? only counts in the decision-ish zone: second person / confirm / or
    if re.search(r"(?i)\b(you|your|we|shall|should|ok\b|okay|confirm|prefer|approve)\b", line):
        return True
    return False


def _extract_need(text: str, limit: int = 6) -> list[str]:
    if not text:
        return []
    text = _strip_fenced_code(text)
    needs: list[str] = []
    seen: set[str] = set()
    lines = text.splitlines()
    # Prefer the closing stretch of the message (where real asks live).
    start = max(0, int(len(lines) * 0.4)) if len(lines) > 12 else 0
    ordered = list(enumerate(lines))
    # Scan end-first for ranking, but keep first-seen order of strong hits in end zone.
    candidates: list[tuple[int, str, bool]] = []
    for idx, raw in ordered[start:]:
        line = raw.strip().lstrip("#*-• ").strip()
        if not line or len(line) < 8:
            continue
        strong = any(p.search(line) for p in NEED_STRONG)
        if strong or _is_need_line(line):
            candidates.append((idx, line[:240], strong))
    # Strong first, then later lines
    candidates.sort(key=lambda t: (0 if t[2] else 1, -t[0]))
    for _, line, _ in candidates:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        needs.append(line)
        if len(needs) >= limit:
            break
    # Fallback: only last 25% of text, strong-ish sentence with ?
    if not needs and "?" in text:
        tail = text[int(len(text) * 0.75) :]
        for para in reversed(re.split(r"\n\s*\n", tail)):
            para = para.strip()
            if "?" not in para:
                continue
            for sent in re.split(r"(?<=[?])\s+", para):
                s = sent.strip()
                if "?" in s and _is_need_line(s):
                    needs.append(s[:240])
                    break
            if needs:
                break
    return needs[:limit]


def _tail_bytes(path: Path, max_bytes: int = 400_000) -> str:
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()  # drop partial first line
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _updates_tool_titles(updates_path: Path, limit: int = 12) -> list[str]:
    """Bounded tail of updates.jsonl → recent tool_call titles for richer HAPPENED."""
    raw = _tail_bytes(updates_path)
    if not raw:
        return []
    titles: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or "tool_call" not in line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        u = (o.get("params") or {}).get("update") or o.get("update") or o
        if u.get("sessionUpdate") != "tool_call":
            continue
        title = u.get("title") or ""
        if not title:
            # fall back to kind / tool name fields
            title = str(u.get("toolName") or u.get("kind") or "")
        title = str(title).strip()
        if title:
            titles.append(title[:120])
    # Keep the last N unique-ish titles from this tail (current turn-ish)
    if not titles:
        return []
    recent = titles[-40:]
    # Compact: count occurrences
    counts: Counter[str] = Counter(recent)
    items = counts.most_common(limit)
    out = []
    for name, n in items:
        out.append(f"{name}×{n}" if n > 1 else name)
    return out


def _merge_happened(event_lines: list[str], update_titles: list[str]) -> list[str]:
    """Prefer event tallies; append update titles when they add names events lack."""
    if not update_titles:
        return event_lines
    if not event_lines or event_lines == ["no tools in last turn"]:
        return [f"tools: {', '.join(update_titles[:8])}"]
    joined = " ".join(event_lines).lower()
    extras = []
    for t in update_titles:
        head = t.split("×")[0].split(":")[0].strip().lower()
        token = head.split()[0] if head else ""
        if token and token not in joined and head not in joined:
            extras.append(t)
    if not extras:
        return event_lines
    merged = list(event_lines)
    merged.append("also: " + ", ".join(extras[:6]))
    return merged[:12]


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
                "loop_active": False,
                "loop_modes": [],
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

    used_updates = False
    update_titles = _updates_tool_titles(sdir / "updates.jsonl")
    if update_titles:
        used_updates = True
        happened = _merge_happened(happened, update_titles)

    if not happened:
        happened = ["no tools in last turn"]

    # Loop / harness label (read-only; never controls agents)
    from .loop import detect_loop_modes

    workspace = cwd or summary.get("info", {}).get("cwd") or os.environ.get("GROK_WORKSPACE_ROOT")
    loop_modes = detect_loop_modes(cwd=workspace, session_id=sid)

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
            "updates": used_updates,
            "model": False,
        },
        "redacted": False,
        "stale": status == "missing",
        "parent_only": parent_only,
        "loop_active": bool(loop_modes),
        "loop_modes": loop_modes,
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
    sdir = Path(card["session_dir"]) if card.get("session_dir") else None
    from .loop import should_write_this_stop

    ok, reason = should_write_this_stop(sdir, list(card.get("loop_modes") or []))
    if not ok:
        card = dict(card)
        card["throttled"] = True
        card["throttle_reason"] = reason
        return redact_card(card)
    write_card(card, cwd=cwd)
    return card
