"""Secret-safe redaction for digests.

Applied to every string field before write. Prefer over-redact.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, MutableMapping

# Order matters: more specific patterns first.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_PAT]"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bxai-[A-Za-z0-9]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b(authorization|api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\b(export\s+)?([A-Z][A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|ACCESS_KEY)[A-Z0-9_]*)\s*=\s*\S+"), r"\1\2=[REDACTED]"),
    # Long opaque tokens (base64-ish)
    (re.compile(r"\b[A-Za-z0-9+/]{48,}={0,2}\b"), "[REDACTED_BLOB]"),
]


def redact_text(text: str | None) -> str:
    if not text:
        return ""
    out = str(text)
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    return out


def redact_card(card: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-copied card with all string fields redacted."""
    out: dict[str, Any] = dict(card)
    for key in ("happened", "attention", "need_from_you"):
        vals = out.get(key) or []
        out[key] = [redact_text(v) for v in vals]
    if out.get("next") is not None:
        out["next"] = redact_text(out.get("next"))
    out["redacted"] = True
    return out


def looks_like_secret(text: str) -> bool:
    if not text:
        return False
    return redact_text(text) != text
