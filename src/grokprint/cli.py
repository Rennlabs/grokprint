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
        if card.get("extract_ms") is not None and float(card["extract_ms"]) > 2000:
            print("WARN: extract > 2000ms on this session", file=sys.stderr)
            return 3
    return 0 if sdir else 1


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
