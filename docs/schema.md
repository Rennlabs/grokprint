# Grokprint card schema

Machine schema: [`schema/grokprint.schema.json`](../schema/grokprint.schema.json).

## Turn boundary

A **turn** is the closed interval in `events.jsonl`:

```
turn_started → … → turn_ended
```

If `turn_ended` is missing when Stop fires, status is `in_progress` and the open buffer is used.

Primary facts come from:

| Event | Use |
|-|-|
| `tool_started` / `tool_completed` | HAPPENED tallies; non-success → ATTENTION |
| `permission_resolved` (not allow) | ATTENTION |
| `turn_ended.outcome` | `completed` / `cancelled` / `error` |
| `chat_history.jsonl` last assistant | NEED heuristics (`?`, confirm/approve language) |

## Redaction

All string fields pass `redact_text` before write. Patterns include private keys, GitHub tokens, `sk-` / `xai-` keys, Bearer tokens, `SECRET|TOKEN|PASSWORD` env assignments, long base64 blobs. Prefer over-redact.

## Surfaces

| Path | Role |
|-|-|
| `<session>/grokprint.json` | Writer of record |
| `<session>/last-print.md` | Human card |
| `<workspace>/.grokprint/last-print.md` | Quick access copy |
| `grokprint show` | CLI |
| Notification hook | NEED-first one-liner |

Annotations (`GROKPRINT_ANNOTATE=1`) are **off by default**.
