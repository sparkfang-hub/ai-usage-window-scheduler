#!/bin/sh
set -eu

REPO_URL="https://github.com/sparkfang-hub/ai-usage-window-scheduler.git"
REF="${AI_WINDOW_REF:-main}"
PREFIX="${AI_WINDOW_PREFIX:-$HOME/.local/share/ai-window}"
VENV="$PREFIX/venv"
BIN_DIR="$HOME/.local/bin"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "AI Window's automatic scheduler currently targets macOS." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

mkdir -p "$PREFIX" "$BIN_DIR"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV/bin/python" -m pip install --upgrade "git+$REPO_URL@$REF"
ln -sf "$VENV/bin/ai-window" "$BIN_DIR/ai-window"

echo
echo "Installed AI Usage Window Scheduler."
echo "Binary: $BIN_DIR/ai-window"
echo
echo "If 'ai-window' is not found, add this to ~/.zshrc:"
echo '  export PATH="$HOME/.local/bin:$PATH"'
echo
echo "Next:"
echo "  ai-window doctor claude"
echo "  ai-window setup claude --work-start 09:00 --lead-minutes 120 --days weekdays --install"
echo "  ai-window test claude"
echo "  ai-window status"
