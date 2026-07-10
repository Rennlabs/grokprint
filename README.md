# grokprint

> **Unofficial** turn-level orientation print for [Grok Build](https://grok.x.ai/).  
> **Not affiliated with xAI.** Best-effort. Session file formats may change without notice.

After a fast, tool-heavy turn, glance at a card instead of scrolling the whole stream:

1. **HAPPENED** — tools / outcomes  
2. **ATTENTION** — failures, denials, risks  
3. **NEED FROM YOU** — questions to answer  

Not a second transcript. An orientation card at the turn boundary.  
**Observer only** — never blocks the agent, never drives loops (safe beside OMC / ralph / harness stacks).

**Status:** public alpha `v0.1.0` · MIT · Python 3.10+

---

## Quick start

```bash
git clone https://github.com/Rennlabs/grokprint.git
cd grokprint
./install.sh
# reload hooks in Grok: Ctrl+L → Hooks → r
```

Or:

```bash
pip install -e .
python -m grokprint doctor
# wire hooks: ./install.sh
```

After any turn:

```bash
grokprint show          # last card
grokprint extract       # re-run extract now
grokprint doctor        # paths, latency, events schema probe
```

Cards land at:

- `~/.grok/sessions/<cwd-enc>/<session-id>/grokprint.json`
- `…/last-print.md`
- `<workspace>/.grokprint/last-print.md` (copy)

If you **move the clone**, re-run `./install.sh` (or keep using `python -m grokprint.hook` after `pip install -e .`).

---

## How it works

| Layer | Role |
|-|-|
| **Stop hook** | Deterministic floor from `events.jsonl` (`turn_started`…`turn_ended`, tools) |
| **chat_history** | Heuristic NEED (decision language, not every `?`) |
| **updates.jsonl** | Extra tool titles when events are thin |
| **Model skill** (optional) | Semantic ceiling for NEED/ATTENTION when non-`none` |
| **Sticky TUI strip** | [Feature request](docs/FEATURE-REQUEST-sticky-strip.md) — not shipped |

**Parent-only** by default (no `SubagentStop`).  
**Annotations off** by default (`GROKPRINT_ANNOTATE=0`).  
**No LLM in the hook.** Fail-open, short timeout.

---

## Config

```bash
GROKPRINT_DISABLE=1     # no-op hook
GROKPRINT_ANNOTATE=1    # compact card as hook annotation (adds scroll)
GROKPRINT_DEBUG=1       # stderr on hook errors
GROKPRINT_LOOP_EVERY=5  # while a harness loop is active, write every Nth Stop
GROKPRINT_LIVE=1 pytest tests/test_harness_latency.py
```

Optional notification helper — `~/.grok/config.toml`:

```toml
[[ui.notifications.hooks]]
command = "msg=$(/path/to/grokprint/hooks/notify_print.sh); notify-send Grok \"$msg\" 2>/dev/null || true"
events = ["turn_complete", "approval_required"]
only_unfocused = true
timeout_secs = 5
```

---

## Stability & support

- Parses **local, unofficial** Grok session artifacts. There is **no compatibility guarantee** across Grok updates.
- Support is **best-effort, no SLA**. Issues welcome; fixes as time allows.
- Security: see [SECURITY.md](SECURITY.md). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).
- Scenario QA: [docs/SCENARIOS.md](docs/SCENARIOS.md).

---

## Develop

```bash
pip install -e .
python -m pytest tests/ -q
```

Schema: [`schema/grokprint.schema.json`](schema/grokprint.schema.json)

## License

[MIT](LICENSE) · Copyright © 2026 Renn Labs

Grok® is a trademark of xAI. This project is independent and unofficial.
