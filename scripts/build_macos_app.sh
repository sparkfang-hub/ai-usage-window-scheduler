#!/bin/bash
set -euo pipefail

APP_NAME="AI Usage Window Scheduler"
BUNDLE_ID="com.sparkfang.aiusagewindowscheduler"
VERSION="${VERSION:-0.3.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
BUILD="$ROOT/build"

cd "$ROOT"
rm -rf "$DIST" "$BUILD" "${APP_NAME}.spec"

python -m pip install --upgrade pip
python -m pip install -e '.[widget]'
python -m pip install 'pyinstaller>=6.10,<7'

python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --osx-bundle-identifier "$BUNDLE_ID" \
  --hidden-import ai_window.widget \
  --hidden-import ai_window.onboarding \
  --hidden-import ai_window.frozen_support \
  --collect-all rumps \
  src/ai_window/app_main.py

APP="$DIST/$APP_NAME.app"
PLIST="$APP/Contents/Info.plist"

/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST"

# Ad-hoc signing makes the bundle internally consistent. A future Developer ID
# certificate can replace this step for notarized public releases.
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

ZIP="$DIST/AI-Usage-Window-Scheduler-macOS-arm64-v${VERSION}.zip"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

DMG_ROOT="$BUILD/dmg"
mkdir -p "$DMG_ROOT"
cp -R "$APP" "$DMG_ROOT/"
ln -s /Applications "$DMG_ROOT/Applications"
DMG="$DIST/AI-Usage-Window-Scheduler-macOS-arm64-v${VERSION}.dmg"
hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$DMG_ROOT" \
  -ov \
  -format UDZO \
  "$DMG"

(
  cd "$DIST"
  shasum -a 256 "$(basename "$ZIP")" "$(basename "$DMG")" > SHA256SUMS.txt
)

printf '\nBuilt:\n  %s\n  %s\n  %s\n' "$APP" "$ZIP" "$DMG"
