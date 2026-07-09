"""Human-facing renderers for Grokprint cards."""

from __future__ import annotations

from typing import Any, Mapping


def _bullets(items: list[str], empty: str = "none") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {x}" for x in items)


def render_markdown(card: Mapping[str, Any]) -> str:
    status = card.get("status") or "?"
    turn = card.get("turn_number")
    turn_s = f"turn {turn}" if turn is not None else "turn ?"
    sid = str(card.get("session_id") or "")[:8]
    ms = card.get("extract_ms")
    ms_s = f" · {ms}ms" if ms is not None else ""
    stale = " · STALE" if card.get("stale") else ""

    lines = [
        f"# GROKPRINT · {status} · {turn_s} · {sid}…{ms_s}{stale}",
        "",
        "## HAPPENED",
        _bullets(list(card.get("happened") or [])),
        "",
        "## ATTENTION",
        _bullets(list(card.get("attention") or []), empty="none"),
        "",
        "## NEED FROM YOU",
        _bullets(list(card.get("need_from_you") or []), empty="none"),
    ]
    nxt = card.get("next")
    if nxt:
        lines.extend(["", f"**NEXT:** {nxt}"])
    lines.append("")
    return "\n".join(lines)


def render_compact(card: Mapping[str, Any], max_lines: int = 12) -> str:
    """≤12 line terminal-friendly card."""
    lines: list[str] = []
    status = card.get("status") or "?"
    lines.append(f"GROKPRINT [{status}] t{card.get('turn_number', '?')}")

    def section(title: str, items: list[str], empty: str = "none") -> None:
        lines.append(f"{title}:")
        if not items:
            lines.append(f"  {empty}")
            return
        for it in items:
            lines.append(f"  • {it}")

    section("HAPPENED", list(card.get("happened") or []))
    section("ATTENTION", list(card.get("attention") or []))
    section("NEED FROM YOU", list(card.get("need_from_you") or []))
    if card.get("next"):
        lines.append(f"NEXT: {card['next']}")

    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + ["  …"]
    return "\n".join(lines)


def render_notification(card: Mapping[str, Any], max_len: int = 200) -> str:
    """Notification body: NEED first, then attention, then happened."""
    need = list(card.get("need_from_you") or [])
    attention = list(card.get("attention") or [])
    happened = list(card.get("happened") or [])
    status = card.get("status") or "?"

    parts: list[str] = []
    if need:
        parts.append("NEED: " + need[0])
    elif attention:
        parts.append("ATTN: " + attention[0])
    elif happened:
        parts.append("OK: " + happened[0])
    else:
        parts.append(f"turn {status}")

    if need and attention:
        parts.append("ATTN: " + attention[0])
    msg = " | ".join(parts)
    if len(msg) > max_len:
        return msg[: max_len - 1] + "…"
    return msg
