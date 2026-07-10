#!/usr/bin/env python3
"""Backward-compatible Stop hook. Prefer: python3 -m grokprint.hook """
from __future__ import annotations

import sys
from pathlib import Path

_HOOK_DIR = Path(__file__).resolve().parent
_REPO = _HOOK_DIR.parent
_SRC = _REPO / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from grokprint.hook import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
