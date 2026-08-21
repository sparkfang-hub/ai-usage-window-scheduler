#!/bin/sh
set -eu

REPO_URL="https://github.com/sparkfang-hub/ai-usage-window-scheduler.git"
REF="${AI_WINDOW_REF:-main}"
PREFIX="${AI_WINDOW_PREFIX:-$HOME/.local/share/ai-window}"
VENV="$PREFIX/venv"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/Applications/AI Usage Window Scheduler.app"
APP_EXEC="$APP_DIR/Contents/MacOS/AI Usage Window Scheduler"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "AI Usage Window Scheduler currently targets macOS." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

mkdir -p "$PREFIX" "$BIN_DIR"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV/bin/python" -m pip install --upgrade "ai-usage-window-scheduler[widget] @ git+$REPO_URL@$REF"
ln -sf "$VENV/bin/ai-window" "$BIN_DIR/ai-window"

mkdir -p "$APP_DIR/Contents/MacOS"
cat > "$APP_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>AI Usage Window Scheduler</string>
  <key>CFBundleDisplayName</key><string>AI Usage Window Scheduler</string>
  <key>CFBundleIdentifier</key><string>com.aiwindow.scheduler</string>
  <key>CFBundleVersion</key><string>0.3.2</string>
  <key>CFBundleShortVersionString</key><string>0.3.2</string>
  <key>CFBundleExecutable</key><string>AI Usage Window Scheduler</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
</dict>
</plist>
PLIST

cat > "$APP_EXEC" <<EOF
#!/bin/sh
exec "$VENV/bin/python" -m ai_window.onboarding
EOF
chmod +x "$APP_EXEC"

"$VENV/bin/ai-window" install-widget >/dev/null 2>&1 || true

printf '\nInstalled AI Usage Window Scheduler.\n'
printf 'App: %s\n' "$APP_DIR"
printf 'Menu bar widget: enabled\n\n'

"$VENV/bin/python" -m ai_window.onboarding

printf '\nDone. Normal users do not need Terminal again.\n'
printf 'Open AI Usage Window Scheduler from ~/Applications to change the time.\n'
