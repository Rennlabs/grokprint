"""Human-facing renderers for Grokprint cards."""

from __future__ import annotations

from typing import Any, Mapping


def _bullets(items: list[str], empty: str = "none") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {x}" for x in items)


def _width() -> int:
    try:
        import os

        return max(40, min(120, int(os.environ.get("COLUMNS") or "80")))
    except (TypeError, ValueError):
        return 80


def _clip(s: str, width: int | None = None) -> str:
    w = width if width is not None else _width()
    s = "".join(ch for ch in s if ch >= " " or ch in "\t")
    if len(s) <= w:
        return s
    return s[: w - 1] + "…"


def render_markdown(card: Mapping[str, Any]) -> str:
    from grokprint import __version__

    status = card.get("status") or "?"
    turn = card.get("turn_number")
    turn_s = f"turn {turn}" if turn is not None else "turn ?"
    sid = str(card.get("session_id") or "")[:8]
    ms = card.get("extract_ms")
    ms_s = f" · {ms}ms" if ms is not None else ""
    stale = " · STALE" if card.get("stale") else ""

    loop = ""
    if card.get("loop_active") and card.get("loop_modes"):
        loop = " · loop:" + ",".join(card["loop_modes"])
    elif card.get("loop_active"):
        loop = " · loop"
    thr = " · throttled" if card.get("throttled") else ""

    lines = [
        f"# GROKPRINT · {status} · {turn_s} · {sid}…{ms_s}{stale}{loop}{thr}",
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
    lines.extend(["", f"_grokprint {__version__}_", ""])
    return "\n".join(lines)


def render_compact(card: Mapping[str, Any], max_lines: int = 12) -> str:
    """≤12 line terminal-friendly card (width-aware)."""
    from grokprint import __version__

    w = _width()
    lines: list[str] = []
    status = card.get("status") or "?"
    loop = ""
    if card.get("loop_modes"):
        loop = " loop:" + ",".join(card["loop_modes"][:3])
    lines.append(_clip(f"GROKPRINT [{status}] t{card.get('turn_number', '?')}{loop} · v{__version__}", w))

    def section(title: str, items: list[str], empty: str = "none") -> None:
        lines.append(_clip(f"{title}:", w))
        if not items:
            lines.append(_clip(f"  {empty}", w))
            return
        for it in items:
            lines.append(_clip(f"  • {it}", w))

    section("HAPPENED", list(card.get("happened") or []))
    section("ATTENTION", list(card.get("attention") or []))
    section("NEED FROM YOU", list(card.get("need_from_you") or []))
    if card.get("next"):
        lines.append(_clip(f"NEXT: {card['next']}", w))

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
