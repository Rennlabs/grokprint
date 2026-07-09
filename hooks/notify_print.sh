#!/usr/bin/env bash
# Grok notification hook helper: emit NEED-first body for turn_complete.
# Usage from config.toml:
#   [[ui.notifications.hooks]]
#   command = "/path/to/grokprint/hooks/notify_print.sh"
#   events = ["turn_complete", "approval_required"]
#   only_unfocused = true
#   timeout_secs = 5
#
# Or chain with a notifier:
#   command = "msg=$(/path/to/hooks/notify_print.sh); notify-send Grok \"$msg\""

set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [[ -L "$SOURCE" ]]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
ROOT="$(cd -P "$(dirname "$SOURCE")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export GROKPRINT_ROOT="${GROKPRINT_ROOT:-$ROOT}"

SESSION="${GROK_SESSION_ID:-}"
CWD="${GROK_WORKSPACE_ROOT:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"

if [[ -n "${GROKPRINT_DISABLE:-}" ]]; then
  echo "${GROK_MESSAGE:-turn complete}"
  exit 0
fi

# Prefer existing card; refresh if missing
if ! python3 -m grokprint.cli notify-body ${SESSION:+--session "$SESSION"} --cwd "$CWD" 2>/dev/null; then
  echo "${GROK_MESSAGE:-Grok turn complete}"
fi
