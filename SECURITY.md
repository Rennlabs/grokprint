# Security Policy

## Scope

**grokprint** is an unofficial local tool. It reads Grok session files under
`~/.grok/sessions/` and writes orientation cards (`grokprint.json`,
`last-print.md`). It does not phone home.

## What we care about

1. **Secret leakage in cards** — tool args and chat text can contain tokens.
   Digests pass through redaction (`src/grokprint/redaction.py`) before write.
   Prefer over-redact; report misses with a **redacted** repro fixture.
2. **Hooks fail-open** — Stop hooks must never block the agent on error.
3. **No credentials in the repo** — never commit `.env`, session dumps, or real tokens.

## Reporting

Open a GitHub issue with the `security` label, or email the maintainers via the
org contact on GitHub. Do **not** attach real secrets; use synthetic fixtures.

## Supported versions

Best-effort on the latest `main` / latest release tag only. There is no paid SLA.

## Threat model (short)

| Asset | Risk | Mitigation |
|-|-|-|
| Session transcripts on disk | Cards re-surface content | Redaction; parent-only; local files only |
| Hook execution | Malicious project hooks | Grok folder-trust; this project only writes digests |
| Install | Path confusion | Prefer `pip install -e .` + `python -m grokprint.hook` |
