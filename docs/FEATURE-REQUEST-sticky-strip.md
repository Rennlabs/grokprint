# Feature request: sticky turn-print strip in Grok TUI

**Status:** community draft / wishlist (unofficial; not an xAI product request channel)  
**Project:** [Rennlabs/grokprint](https://github.com/Rennlabs/grokprint)  
**Date:** 2026-07-09

## Problem

Grok Build streams tool output so quickly that the user loses:

1. What just happened (tools / files / outcomes)
2. What needs attention (failures / risks)
3. What they must answer or decide next

Scrollback fold/expand and session titles help, but they do not pin an **action-oriented turn digest** at the edge of the viewport.

## What we built out-of-band

`grokprint` already provides:

- Deterministic extract on `Stop` from `events.jsonl` (`turn_started` / `turn_ended` / `tool_*`)
- `grokprint.json` + `last-print.md` per session
- CLI: `grokprint show | extract | doctor | notify-body`
- Optional notification body with NEED-first text

**Gap:** hooks are passive; digests live in files / optional annotations. True zero-scroll UX needs a **native sticky surface**.

## Requested UX

At end of each agent turn, pin a compact strip (3–6 lines) above the prompt:

```
GROKPRINT [completed] t12 · 48ms
HAPPENED  12 tools: edit×4, bash×3 …
ATTENTION test failed: …
NEED      Approve deploy to staging?
```

Behaviors:

| Behavior | Spec |
|-|-|
| Pinning | Always visible while idle; does not scroll away with tool noise |
| Expand | `e` / click expands full card; collapses by default |
| Source | Prefer session `grokprint.json` if present; else native extract |
| Subagents | Parent turn only by default |
| Opt-out | `ui.grokprint.enabled = false` |
| Accessibility | Plain text; no color-only status |

## Why not only hooks?

| Hook capability today | Sticky strip need |
|-|-|
| Passive Stop; stdout not control plane | First-class UI widget |
| Annotations add scrollback noise | Pin outside scroll stream |
| `$GROK_MESSAGE` unstructured | Structured sections |

## Suggested config

```toml
[ui.grokprint]
enabled = true
max_lines = 6
show_happened = true
show_attention = true
show_need = true
parent_only = true
```

## Success metrics

- Time-to-reorient after a 50+ tool turn: &lt; 2s without scrolling
- NEED section non-empty whenever the final assistant message contains a question (measure on fixtures)
- Zero secret leakage (same redaction contract as grokprint)

## Offer

Rennlabs/grokprint can remain the reference extract + schema. Happy to align field names if the TUI lands a native strip.
