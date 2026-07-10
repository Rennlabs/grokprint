# Contributing

Thanks for interest in **grokprint** (unofficial Grok Build turn-print).

## Dev setup

```bash
git clone https://github.com/Rennlabs/grokprint.git
cd grokprint
python3 -m pip install -e ".[dev]"  # or: pip install -e . && pip install pytest
python3 -m pytest tests/ -q
./install.sh   # optional: wire Stop hook for local Grok
```

## Guidelines

1. Keep the Stop hook **fail-open**, **no LLM**, **parent-only** (no SubagentStop).
2. Add fixtures under `tests/fixtures/` for extract/NEED/redaction changes.
3. Do not treat digests as an agent control protocol (see `AGENTS.md`).
4. Small PRs; run `pytest` before pushing.

## PR checklist

- [ ] Tests pass
- [ ] No secrets in fixtures (synthetic only)
- [ ] README/docs updated if behavior changes
- [ ] CHANGELOG note under Unreleased (or next version)

## Code of conduct

Be respectful. This is a small best-effort project.
