# Standalone package validation

Validated on GitHub Actions `macos-15-arm64` for v0.3.0.

- Python unit tests: passed
- CLI package version check: passed (`0.3.0`)
- PyInstaller standalone `.app` build: passed
- ad-hoc codesign verification: passed
- bundled executable smoke test: passed
- `.zip` packaging: passed
- `.dmg` packaging: passed
- SHA-256 generation: passed
- GitHub Actions artifact upload: passed

Latest validated artifact files:

- `AI-Usage-Window-Scheduler-macOS-arm64-v0.3.0.dmg`
- `AI-Usage-Window-Scheduler-macOS-arm64-v0.3.0.zip`
- `SHA256SUMS.txt`

Validated DMG SHA-256:

`fe40f7001fbfc7cce01d4fb3920e6cb44591a4e292fe378b98b392a69edccb6d`

The app is not Apple-notarized yet. First launch on another Mac may require Control-click / right-click → Open until Developer ID signing and notarization are configured.
