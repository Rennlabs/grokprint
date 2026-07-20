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
DRY_RUN=0
FORCE=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [OPTIONS]

Install grokprint (editable package + Grok Stop hooks + CLI).

Options:
  --dry-run     Print actions; mutate nothing
  --force       Backup foreign CLI path, then replace symlink
  -h, --help    Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "install.sh: unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

log() { printf '%s\n' "$*"; }

if [[ "$DRY_RUN" -eq 1 ]]; then
  log "[dry-run] would mkdir -p $GROK_HOME/hooks $BIN_DIR $GROK_HOME/skills"
  log "[dry-run] would pip install -e $ROOT (or PYTHONPATH fallback)"
  log "[dry-run] would write $GROK_HOME/hooks/grokprint-stop.json"
  log "[dry-run] would symlink $ROOT/bin/grokprint -> $BIN_DIR/grokprint"
  [[ -d "$ROOT/skills/grokprint" ]] && log "[dry-run] would symlink skill -> $GROK_HOME/skills/grokprint"
  log "[dry-run] complete — no files modified"
  log "After real install: reload hooks in Grok via Ctrl+L → Hooks → r"
  exit 0
fi

mkdir -p "$GROK_HOME/hooks" "$BIN_DIR" "$GROK_HOME/skills"

echo "Installing package (editable) from $ROOT …"
if ! "$PYTHON" -m pip install -e "$ROOT" -q 2>/dev/null; then
  echo "pip install -e failed; falling back to PYTHONPATH via wrapper only."
fi

# Prefer module entry so relocating the repo still works after re-install.
# Build hook command via python shlex so paths with spaces stay safe in JSON.
HOOK_JSON="$GROK_HOME/hooks/grokprint-stop.json"
python3 - "$PYTHON" "$ROOT" "$ANNOTATE" "$HOOK_JSON" <<'PY'
import json, shlex, subprocess, sys
from pathlib import Path

python, root, annotate, hook_json = sys.argv[1:5]
# Prefer importable package; else PYTHONPATH wrapper with quoted paths.
cmd = f"{shlex.quote(python)} -m grokprint.hook"
try:
    subprocess.check_call([python, "-c", "import grokprint"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except Exception:
    cmd = f"env PYTHONPATH={shlex.quote(root + '/src')} {shlex.quote(python)} -m grokprint.hook"

hook = {
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": cmd,
        "timeout": 5,
        "env": {"GROKPRINT_ANNOTATE": annotate},
      }]
    }],
    "StopFailure": [{
      "hooks": [{
        "type": "command",
        "command": cmd,
        "timeout": 5,
        "env": {"GROKPRINT_ANNOTATE": annotate},
      }]
    }],
  }
}
Path(hook_json).write_text(json.dumps(hook, indent=2) + "\n", encoding="utf-8")
print("wrote", hook_json)
print("hook command:", cmd)
PY

CLI_DST="$BIN_DIR/grokprint"
CLI_SRC="$ROOT/bin/grokprint"
if [[ -L "$CLI_DST" ]] || [[ ! -e "$CLI_DST" ]]; then
  ln -sfn "$CLI_SRC" "$CLI_DST"
elif [[ "$FORCE" -eq 1 ]]; then
  bak="${CLI_DST}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$CLI_DST" "$bak"
  ln -s "$CLI_SRC" "$CLI_DST"
  echo "backed up $CLI_DST -> $bak"
else
  echo "WARN: $CLI_DST exists and is not a symlink; skip (use --force)" >&2
fi
chmod +x "$ROOT/bin/grokprint" "$ROOT/hooks/stop_print.py" "$ROOT/hooks/notify_print.sh" "$ROOT/install.sh"

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
