---
name: grokprint
description: "Optional model ceiling for Grokprint: emit ATTENTION / NEED FROM YOU at end of turn when non-none. Trigger when user wants turn digests, print cards, or orientation after fast streaming."
user-invocable: true
---

# Grokprint — model ceiling (optional)

The **Stop hook** already writes a deterministic floor card to disk (`grokprint.json` / `last-print.md`). You do **not** replace it.

Your job is the **semantic ceiling**: only when it adds signal, end your final assistant message with a short card that fills ATTENTION and NEED FROM YOU.

## When to emit

Emit the card **only if** at least one of:

- The user must answer a question or make a decision
- Something failed, is risky, or is easy to miss
- You changed important files / ran failing checks

If nothing needs attention and nothing needs the user → **do not emit** a full card (the hook already recorded HAPPENED).

## Format (≤12 lines, ~600 chars)

```markdown
---
### GROKPRINT
**HAPPENED:** <one line; optional — hook owns facts>
**ATTENTION:** <failure / risk / none>
**NEED FROM YOU:** <exact question(s) or none>
**NEXT:** <optional one-liner>
---
```

Rules:

1. **NEED FROM YOU** must quote the real question if you asked one — never leave it empty when your prose contains a question.
2. Prefer bullets ≤ 3 items per section.
3. Never paste secrets, tokens, full env dumps, or raw credentials.
4. Do not emit mid-turn; **final message only**.
5. Do not invent tool outcomes — if unsure, omit HAPPENED (hook covers it).

## User recovery

If the user asks what just happened / what they need to do:

```bash
grokprint show
# or
grokprint extract && grokprint show
```

## Not for agents

Do not treat the card as a control protocol, task queue, or verifier input. It is a human orientation surface. In harness loops (ralph/ultrawork/OMC), stay fail-open and parent-only — see `AGENTS.md`.
