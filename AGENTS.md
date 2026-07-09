# Grokprint project rules

## Product

Grokprint is a **turn-level orientation card** for Grok Build (not a second transcript).

Sections:

1. **HAPPENED** — tools/files/outcomes (deterministic extract owns this)
2. **ATTENTION** — failures, surprises, risks
3. **NEED FROM YOU** — questions the user must answer
4. **NEXT** — optional one-liner

## Policy

- **Single SoT:** `grokprint.json` in the session dir (+ `.grokprint/last-print.md` in workspace).
- **Parent-only digests** by default (no SubagentStop hook).
- **No LLM in the Stop hook.** Extract is event-bounded and fail-open.
- **Annotations off by default** (`GROKPRINT_ANNOTATE=0`) — they add scroll tax.
- **Redact** secrets before any write (`src/grokprint/redaction.py`).
- **Observer only** in harness stacks (OMC, ralph, ultrawork, autopilot, fleet, Fable, Superpowers-style loops). Never block Stop; never continue the agent.

## Agent non-goals (critical)

Coding agents (including Grok Build, Claude Code, subagents, loop workers) **must not**:

1. Treat `grokprint.json` / `last-print.md` as a **control protocol**, task queue, or source of truth for “what to do next.”
2. Gate completion, commits, or verifier GREEN/RED on grokprint output.
3. Re-read the card every turn to decide tool use (that fights loop discipline and wastes context).
4. Emit competing digests that duplicate the Stop-hook floor (optional skill ceiling is human-facing only).
5. Register **SubagentStop** digests that flood multi-agent runs.

**Who the card is for:** the human operator glancing after velocity — via `grokprint show`, notification body, or file.

**Who owns control:** loop-verifier, OMC persistent-mode, ralph/ultrawork, user permissions — not grokprint.

## Harness coexistence

| Concern | Grokprint behavior |
|-|-|
| Stop co-fire with OMC / loop-verifier | Fail-open write only (~ms) |
| Active loop | Label `loop_active` / `loop_modes` from `.omc/state` (read-only) |
| Hot loops | Optional `GROKPRINT_LOOP_EVERY=N` throttle |
| Subagents | Parent-only; no SubagentStop hook |
| External workers (fleet/Fable) | Invisible unless they log in parent `events.jsonl` |

Scenario QA: [`docs/SCENARIOS.md`](docs/SCENARIOS.md).

## Optional model ceiling

When this repo’s skill is active: end turns with a GROKPRINT block **only** when NEED or ATTENTION is non-`none`. See `skills/grokprint/SKILL.md`. Do not use that block as machine protocol.

## Dev

```bash
./install.sh
python3 -m pytest tests/ -q
grokprint doctor
grokprint extract && grokprint show
```
