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

## Optional model ceiling

When this repo’s skill is active: end turns with a GROKPRINT block **only** when NEED or ATTENTION is non-`none`. See `skills/grokprint/SKILL.md`.

## Dev

```bash
./install.sh
python3 -m pytest tests/ -q
grokprint doctor
grokprint extract && grokprint show
```
