#!/usr/bin/env bash
# Install grokprint: editable package + Grok Stop hooks + CLI.
# Path-resilient: hooks invoke ``python3 -m grokprint.hook`` (package on PYTHONPATH / site-packages).
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [[ -L "$SOURCE" ]]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
ROOT="$(cd -P "$(dirname "$SOURCE")" && pwd)"

GROK_HOME="${GROK_HOME:-$HOME/.grok}"
BIN_DIR="${GROKPRINT_BIN_DIR:-$HOME/.local/bin}"
ANNOTATE="${GROKPRINT_ANNOTATE:-0}"
PYTHON="${GROKPRINT_PYTHON:-python3}"

mkdir -p "$GROK_HOME/hooks" "$BIN_DIR" "$GROK_HOME/skills"

echo "Installing package (editable) from $ROOT …"
if ! "$PYTHON" -m pip install -e "$ROOT" -q 2>/dev/null; then
  echo "pip install -e failed; falling back to PYTHONPATH via wrapper only."
fi

# Prefer module entry so relocating the repo still works after re-install.
# Use the same interpreter that can import grokprint.
HOOK_CMD="$PYTHON -m grokprint.hook"
if ! $PYTHON -c "import grokprint" 2>/dev/null; then
  # Fallback: absolute path to package hook with PYTHONPATH
  HOOK_CMD="env PYTHONPATH=$ROOT/src $PYTHON -m grokprint.hook"
fi

HOOK_JSON="$GROK_HOME/hooks/grokprint-stop.json"
python3 - <<PY
import json
from pathlib import Path
hook = {
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": """$HOOK_CMD""",
        "timeout": 5,
        "env": {
          "GROKPRINT_ANNOTATE": "$ANNOTATE",
        }
      }]
    }],
    "StopFailure": [{
      "hooks": [{
        "type": "command",
        "command": """$HOOK_CMD""",
        "timeout": 5,
        "env": {
          "GROKPRINT_ANNOTATE": "$ANNOTATE",
        }
      }]
    }]
  }
}
Path("$HOOK_JSON").write_text(json.dumps(hook, indent=2) + "\n")
print("wrote", "$HOOK_JSON")
print("hook command:", """$HOOK_CMD""")
PY

# CLI wrapper still resolves through symlink for users without PATH to console_scripts
ln -sfn "$ROOT/bin/grokprint" "$BIN_DIR/grokprint"
chmod +x "$ROOT/bin/grokprint" "$ROOT/hooks/stop_print.py" "$ROOT/hooks/notify_print.sh" "$ROOT/install.sh"

# Also try console_script if pip put it somewhere
if [[ -x "$BIN_DIR/grokprint" ]] || command -v grokprint >/dev/null 2>&1; then
  :
fi

if [[ -d "$ROOT/skills/grokprint" ]]; then
  ln -sfn "$ROOT/skills/grokprint" "$GROK_HOME/skills/grokprint"
  echo "skill → $GROK_HOME/skills/grokprint"
fi

echo ""
echo "Installed grokprint (public alpha):"
echo "  hook:  $HOOK_JSON"
echo "  cli:   $BIN_DIR/grokprint  (and/or pip console_script)"
echo "  root:  $ROOT"
echo ""
echo "Reload hooks in Grok: Ctrl+L → Hooks → r  (or /hooks)"
echo "If you move this clone, re-run: $ROOT/install.sh"
echo "Disable: GROKPRINT_DISABLE=1  or  rm $HOOK_JSON"
echo "Annotate scrollback: GROKPRINT_ANNOTATE=1 $0"
