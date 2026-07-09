#!/usr/bin/env bash
# Install grokprint hooks + CLI into the user Grok home.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
GROK_HOME="${GROK_HOME:-$HOME/.grok}"
BIN_DIR="${GROKPRINT_BIN_DIR:-$HOME/.local/bin}"
ANNOTATE="${GROKPRINT_ANNOTATE:-0}"

mkdir -p "$GROK_HOME/hooks" "$BIN_DIR" "$GROK_HOME/skills"

# Expand GROKPRINT_ROOT into a concrete hook JSON (Grok env expansion may be limited).
HOOK_JSON="$GROK_HOME/hooks/grokprint-stop.json"
python3 - <<PY
import json
from pathlib import Path
root = Path("$ROOT").resolve()
hook = {
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": f"python3 {root / 'hooks' / 'stop_print.py'}",
        "timeout": 5,
        "env": {
          "GROKPRINT_ROOT": str(root),
          "GROKPRINT_ANNOTATE": "$ANNOTATE",
        }
      }]
    }],
    "StopFailure": [{
      "hooks": [{
        "type": "command",
        "command": f"python3 {root / 'hooks' / 'stop_print.py'}",
        "timeout": 5,
        "env": {
          "GROKPRINT_ROOT": str(root),
          "GROKPRINT_ANNOTATE": "$ANNOTATE",
        }
      }]
    }]
  }
}
Path("$HOOK_JSON").write_text(json.dumps(hook, indent=2) + "\n")
print("wrote", "$HOOK_JSON")
PY

# CLI
ln -sfn "$ROOT/bin/grokprint" "$BIN_DIR/grokprint"
chmod +x "$ROOT/bin/grokprint" "$ROOT/hooks/stop_print.py" "$ROOT/hooks/notify_print.sh"

# Skill (global Grok skills)
if [[ -d "$ROOT/skills/grokprint" ]]; then
  ln -sfn "$ROOT/skills/grokprint" "$GROK_HOME/skills/grokprint"
  echo "skill → $GROK_HOME/skills/grokprint"
fi

echo ""
echo "Installed grokprint:"
echo "  hook:  $HOOK_JSON"
echo "  cli:   $BIN_DIR/grokprint"
echo "  root:  $ROOT"
echo ""
echo "Reload hooks in Grok: Ctrl+L → Hooks → r  (or /hooks)"
echo "Optional notification hook — add to ~/.grok/config.toml:"
echo ""
cat <<EOF
[[ui.notifications.hooks]]
command = "msg=\$($ROOT/hooks/notify_print.sh); echo \"\$msg\""
events = ["turn_complete", "approval_required"]
only_unfocused = true
timeout_secs = 5
EOF
echo ""
echo "Disable: GROKPRINT_DISABLE=1  or  rm $HOOK_JSON"
echo "Annotate scrollback: reinstall with GROKPRINT_ANNOTATE=1 $0"
