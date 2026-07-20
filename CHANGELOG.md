# Changelog

## [0.1.1] - 2026-07-20

### Added

- `grokprint version` / `--version`
- Doctor reports hook file + **reload** honesty (Ctrl+L → Hooks → r)
- ATTENTION context signals: git dirty path count, latest verifier RED
- Width-aware compact cards (`COLUMNS`); version footer on markdown cards

## [0.1.0] — 2026-07-09

### Added

- Turn-level orientation cards: HAPPENED / ATTENTION / NEED FROM YOU
- Deterministic Stop-hook extract from Grok `events.jsonl` (+ chat heuristics, updates titles)
- CLI: `grokprint show | extract | doctor | notify-body`
- Redaction pass; parent-only policy; optional loop labels from `.omc/state`
- `install.sh` with path-resilient `python -m grokprint.hook` entry
- Scenario checklist, SECURITY, CONTRIBUTING, GitHub Actions CI
- Public alpha positioning (unofficial, best-effort)

### Notes

- Host session format is unofficial and may change without notice.
