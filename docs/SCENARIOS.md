# Grokprint scenario checklist (30)

Manual QA matrix. After a turn that matches the **request**, run:

```bash
grokprint show
# or: cat .grokprint/last-print.md
```

Mark each: **PASS / FAIL / SKIP** and note card quirks.

## Pass criteria (global)

| Field | Pass |
|-|-|
| Pipeline | Auto-Stop or `grokprint extract` produces `completed` (or correct `cancelled`/`error`) |
| HAPPENED | Non-empty when tools ran; tallies compact (≤12 lines) |
| ATTENTION | Non-empty on failures / denials / cancel; else `none` |
| NEED | Non-empty only when the user must answer; empty when “just do it” |
| Safety | No raw secrets/tokens in card |
| Loops | Never blocks agent Stop; parent-only; extract stays fast |

---

## A. Everyday coding (1–10)

| # | Request | Expected HAPPENED | ATTENTION | NEED | Result |
|-|-|-|-|-|-|
| 1 | “What does `extract.py` do?” | reads | none | none | |
| 2 | “Fix the failing test” | edit + test | fail if RED | none or re-run? | |
| 3 | “Add CLI flag `--json`” | edits | none | none | |
| 4 | “Commit this” | git tools | hook reject? | confirm msg? | |
| 5 | “Open a PR” | gh/git | auth fail? | draft/ready? | |
| 6 | “Explain this error: …” | few/none | none | none | |
| 7 | “Rename across repo” | many edits compacted | partial? | API break? | |
| 8 | “Run full test suite” | bash | RED lines | none | |
| 9 | “Plan only, don’t code” | little tools | none | approve plan? | |
| 10 | “Undo the last change” | git/edit | destructive | confirm? | |

## B. Decisions (11–16)

| # | Request | NEED must… | Result |
|-|-|-|-|
| 11 | Postgres vs SQLite? | capture the choice | |
| 12 | Pick one of 3 APIs | numbered options | |
| 13 | Safe to force-push? | confirm + ATTENTION risk | |
| 14 | “Just do it, don’t ask” | **empty** (false NEED = FAIL) | |
| 15 | “What’s next?” after long work | NEXT or clear need | |
| 16 | Multi-question wrap-up | 2–6 real asks, not every `?` | |

## C. Failures & safety (17–22)

| # | Situation | Expected | Result |
|-|-|-|-|
| 17 | Deploy script fails | ATTENTION error | |
| 18 | Permission denied | ATTENTION deny | |
| 19 | Esc / cancel mid-turn | status `cancelled` | |
| 20 | API / StopFailure | status error/missing | |
| 21 | Secret in command | redacted | |
| 22 | Merge conflicts | paths in HAPPENED/ATTENTION | |

## D. Harness / loops / multi-agent (23–30)

| # | Mode / request | Expected print | Agent impact | Result |
|-|-|-|-|-|
| 23 | `/ralph` until green | overwrite each Stop; last wins | must **not** block | |
| 24 | `/ultrawork` | dense tallies; no annotation spam | parent-only | |
| 25 | `/autopilot` | glance between iters | no fight with verifier | |
| 26 | OMC team / omc-teams | parent card only | children silent | |
| 27 | 5 subagents then merge | parent merge turn | no SubagentStop digests | |
| 28 | loop-verifier RED (Claude) | card may look stale | gate owns control | |
| 29 | fleet / Fable workers | parent session only | workers invisible | |
| 30 | overnight sprint many Stops | p95 extract tiny; single SoT | optional history later | |

---

## Harness notes

- Grokprint is an **observer**. Control-plane hooks (loop-verifier, OMC persistent-mode, ralph) may gate or continue agents; grokprint only writes files.
- Active loop detection (read-only): card fields `loop_active` / `loop_modes` when `.omc/state/*-state.json` has `active: true`.
- Throttle writes in hot loops: `GROKPRINT_LOOP_EVERY=5` (write every Nth Stop while a loop is active).
- Never enable SubagentStop digests in multi-agent stacks.

## Log template

```text
Date:
Session:
Scenarios run: #…
Fails:
  - #N: observed … expected …
Follow-ups:
```
