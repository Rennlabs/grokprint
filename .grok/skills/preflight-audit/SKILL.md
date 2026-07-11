---
name: preflight-audit
description: >
  Comprehensive preflight application audit for this repo and others: security, races,
  reliability, a11y, UI consistency. Prefer the user-global skill if both exist; project
  copy documents local convention. Triggers: /preflight-audit, preflight check, ship audit.
---

# Preflight Audit (project pointer)

Use the full workflow from the user skill:

`~/.grok/skills/preflight-audit/SKILL.md`

For this repository’s latest report, see:

`docs/audits/preflight-2026-07-10.md`

**grokprint-specific emphasis:** redaction completeness, project `.grokprint/` copies, turn-bounded extract, atomic writes, Stop-hook fail-open under harness loops, session path sanitisation. Most classic web XSS/CSRF/a11y items are N/A.
