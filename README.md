# grokprint

**Practical turn-level print for [Grok Build](https://grok.x.ai/)** — so after a fast, tool-heavy turn you know:

1. **HAPPENED** — tools / outcomes  
2. **ATTENTION** — failures, denials, risks  
3. **NEED FROM YOU** — questions to answer  

Not a second transcript. An orientation card at the turn boundary.

## Quick start

```bash
git clone git@github.com:Rennlabs/grokprint.git
cd grokprint
./install.sh
# reload hooks in Grok: Ctrl+L → Hooks → r
```

After any turn:

```bash
grokprint show          # last card
grokprint extract       # re-run extract now
grokprint doctor        # paths + latency
```

Cards land at:

- `~/.grok/sessions/<cwd-enc>/<session-id>/grokprint.json`
- `…/last-print.md`
- `<workspace>/.grokprint/last-print.md` (copy)

## How it works

| Layer | Role |
|-|-|
| **Stop hook** | Deterministic floor from `events.jsonl` (`turn_started`…`turn_ended`, tools) |
| **chat_history** | Heuristic NEED (`?`, confirm/approve language) |
| **Model skill** (optional) | Semantic ceiling for NEED/ATTENTION when non-`none` |
| **Notification helper** | NEED-first one-liner for unfocused terminals |
| **Sticky TUI strip** | [Feature request](docs/FEATURE-REQUEST-sticky-strip.md) — not shipped |

**Parent-only** by default (no `SubagentStop` hook).  
**Annotations off** by default (`GROKPRINT_ANNOTATE=0`) — they add scroll tax.  
**No LLM in the hook.** Fail-open, ≤5s timeout.

## Config

```bash
GROKPRINT_DISABLE=1     # no-op hook
GROKPRINT_ANNOTATE=1    # print compact card as hook annotation
GROKPRINT_DEBUG=1       # stderr on hook errors
GROKPRINT_LOOP_EVERY=5  # while a harness loop is active, write every Nth Stop
GROKPRINT_LIVE=1 pytest tests/test_harness_latency.py  # p95 on real sessions
```

Scenario QA checklist: [`docs/SCENARIOS.md`](docs/SCENARIOS.md).  
Harness role: **observer only** — never agent control (see `AGENTS.md`).

Optional notification hook — add to `~/.grok/config.toml`:

```toml
[[ui.notifications.hooks]]
command = "msg=$(/path/to/grokprint/hooks/notify_print.sh); notify-send Grok \"$msg\" 2>/dev/null || echo \"$msg\""
events = ["turn_complete", "approval_required"]
only_unfocused = true
timeout_secs = 5
```

## Develop

```bash
python3 -m pytest tests/ -q
```

Schema: [`schema/grokprint.schema.json`](schema/grokprint.schema.json) · Design notes: [`.omc/plans/esat-2026-07-09-turn-print-summarization.md`](.omc/plans/esat-2026-07-09-turn-print-summarization.md)

## License

MIT
