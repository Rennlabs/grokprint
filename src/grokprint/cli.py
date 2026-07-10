"""CLI entrypoint: grokprint show | extract | doctor | notify-body."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from repo without install
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from grokprint.extract import extract_and_write, extract_card, write_card  # noqa: E402
from grokprint.render import render_compact, render_markdown, render_notification  # noqa: E402
from grokprint.session import find_session_dir, project_last_print_path  # noqa: E402


def _load_card(session_id: str | None, cwd: str | None) -> dict | None:
    sdir = find_session_dir(session_id=session_id, cwd=cwd)
    if sdir is None:
        return None
    path = sdir / "grokprint.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def cmd_show(args: argparse.Namespace) -> int:
    card = _load_card(args.session, args.cwd)
    if card is None:
        # Fall back to project last-print
        proj = project_last_print_path(args.cwd)
        if proj.exists():
            sys.stdout.write(proj.read_text(encoding="utf-8"))
            return 0
        print("No grokprint card found. Run: grokprint extract", file=sys.stderr)
        return 1
    if args.json:
        json.dump(card, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif args.compact:
        sys.stdout.write(render_compact(card) + "\n")
    else:
        sys.stdout.write(render_markdown(card))
    if card.get("stale"):
        return 2
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    card = extract_and_write(
        session_id=args.session,
        cwd=args.cwd,
        parent_only=not args.include_subagents,
        include_chat=not args.no_chat,
    )
    if args.quiet:
        pass
    elif args.json:
        json.dump(card, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_compact(card) + "\n")
    if card.get("status") == "missing":
        return 2
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    sid = args.session or os.environ.get("GROK_SESSION_ID")
    cwd = args.cwd or os.environ.get("GROK_WORKSPACE_ROOT") or os.getcwd()
    sdir = find_session_dir(session_id=sid, cwd=cwd)
    print(f"cwd:          {cwd}")
    print(f"GROK_SESSION: {sid or '(unset)'}")
    print(f"session_dir:  {sdir or '(not found)'}")
    if sdir:
        for name in ("events.jsonl", "updates.jsonl", "chat_history.jsonl", "summary.json", "grokprint.json", "last-print.md"):
            p = sdir / name
            if p.exists():
                print(f"  ✓ {name} ({p.stat().st_size} bytes)")
            else:
                print(f"  · {name} (missing)")
        card = extract_card(session_dir=sdir, parent_only=not args.include_subagents)
        print(f"extract_ms:   {card.get('extract_ms')}")
        print(f"status:       {card.get('status')}")
        print(f"tools lines:  {len(card.get('happened') or [])}")
        print(f"need lines:   {len(card.get('need_from_you') or [])}")
        print(f"loop_active:  {card.get('loop_active')} {card.get('loop_modes') or []}")
        compat = _events_compat_probe(sdir / "events.jsonl")
        print(f"events probe: {compat['summary']}")
        if compat.get("schema_versions"):
            print(f"  schema_version samples: {compat['schema_versions']}")
        if compat.get("types"):
            top = ", ".join(f"{k}×{v}" for k, v in compat["types"][:8])
            print(f"  event types (sample): {top}")
        if not compat.get("ok"):
            print("WARN: events.jsonl missing expected turn markers — Grok format may have changed", file=sys.stderr)
        # Recent Stop co-fire names from updates.jsonl (tail)
        stop_hooks = _recent_stop_hooks(sdir / "updates.jsonl")
        if stop_hooks:
            print("last Stop co-fire:")
            for name, ms in stop_hooks:
                print(f"  · {name} ({ms}ms)" if ms is not None else f"  · {name}")
        if card.get("extract_ms") is not None and float(card["extract_ms"]) > 2000:
            print("WARN: extract > 2000ms on this session", file=sys.stderr)
            return 3
        if not compat.get("ok"):
            return 4
    return 0 if sdir else 1


def _events_compat_probe(events_path: Path, max_lines: int = 5000) -> dict:
    """Sample events.jsonl for turn markers and schema_version (fail-loud on drift)."""
    from collections import Counter

    if not events_path.exists():
        return {"ok": False, "summary": "events.jsonl missing", "types": [], "schema_versions": []}
    types: Counter[str] = Counter()
    schemas: Counter[str] = Counter()
    has_start = has_end = has_tool = False
    n = 0
    try:
        with events_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                n += 1
                if n > max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = str(o.get("type") or "?")
                types[t] += 1
                if t == "turn_started":
                    has_start = True
                    if o.get("schema_version") is not None:
                        schemas[str(o.get("schema_version"))] += 1
                elif t == "turn_ended":
                    has_end = True
                elif t in ("tool_started", "tool_completed"):
                    has_tool = True
    except OSError as exc:
        return {"ok": False, "summary": f"read error: {exc}", "types": [], "schema_versions": []}

    ok = has_start and (has_end or has_tool)
    parts = []
    parts.append("turn_started" if has_start else "NO turn_started")
    parts.append("turn_ended" if has_end else "no turn_ended yet")
    parts.append("tools" if has_tool else "no tools")
    parts.append(f"scanned≤{n} lines")
    return {
        "ok": ok,
        "summary": "; ".join(parts),
        "types": types.most_common(12),
        "schema_versions": [f"{k}×{v}" for k, v in schemas.most_common(5)],
    }


def _recent_stop_hooks(updates_path: Path, max_bytes: int = 200_000) -> list[tuple[str, int | None]]:
    if not updates_path.exists():
        return []
    try:
        size = updates_path.stat().st_size
        with updates_path.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()
            raw = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    last_runs: list[tuple[str, int | None]] = []
    for line in raw.splitlines():
        if "hook_execution" not in line or "stop" not in line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        u = (o.get("params") or {}).get("update") or {}
        if u.get("sessionUpdate") != "hook_execution":
            continue
        if str(u.get("event_name") or "").lower() not in ("stop", "stop_failure"):
            continue
        last_runs = []
        for r in u.get("runs") or []:
            st = r.get("status") or {}
            last_runs.append((str(r.get("name") or "?"), st.get("elapsed_ms")))
    return last_runs


def cmd_notify_body(args: argparse.Namespace) -> int:
    card = _load_card(args.session, args.cwd)
    if card is None:
        card = extract_and_write(session_id=args.session, cwd=args.cwd)
    sys.stdout.write(render_notification(card))
    sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="grokprint",
        description="Practical turn-level print for Grok Build",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--session", default=None, help="Session id (default: GROK_SESSION_ID)")
    common.add_argument("--cwd", default=None, help="Workspace root (default: GROK_WORKSPACE_ROOT or pwd)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="Show last card", parents=[common])
    p_show.add_argument("--json", action="store_true")
    p_show.add_argument("--compact", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_ex = sub.add_parser("extract", help="Extract from session events and write card", parents=[common])
    p_ex.add_argument("--json", action="store_true")
    p_ex.add_argument("--quiet", action="store_true")
    p_ex.add_argument("--no-chat", action="store_true", help="Skip chat_history NEED heuristics")
    p_ex.add_argument("--include-subagents", action="store_true")
    p_ex.set_defaults(func=cmd_extract)

    p_doc = sub.add_parser("doctor", help="Diagnose session paths and extract health", parents=[common])
    p_doc.add_argument("--include-subagents", action="store_true")
    p_doc.set_defaults(func=cmd_doctor)

    p_n = sub.add_parser("notify-body", help="Print notification body (NEED first)", parents=[common])
    p_n.set_defaults(func=cmd_notify_body)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
