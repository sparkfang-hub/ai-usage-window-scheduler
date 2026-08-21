# AI Usage Window Scheduler

**Wake the AI before you need the AI — and keep usage/reset windows visible in one place.**

AI Usage Window Scheduler is a macOS-first utility for people who use several AI tools and do not want to keep checking quota/reset pages manually.

## Normal setup: download, enter one time, done

The intended public install flow is:

```text
Download DMG
   ↓
Drag AI Usage Window Scheduler.app to Applications
   ↓
Open the app
   ↓
每天要幾點自動啟動 Claude？

[ 05:00 ]

      [儲存]
   ↓
Done
```

Normal users do **not** need CLI flags or Terminal after downloading the app.

- The time is the actual wake time.
- It runs every day, including weekends.
- No weekday selector.
- No lead-time setting.
- No model selector.
- The menu-bar usage widget starts automatically.
- Open the app later to change the time.
- The menu-bar widget also includes **Change wake time…**.

### macOS build artifacts

GitHub Actions builds an Apple Silicon standalone package containing its own Python runtime:

```text
AI-Usage-Window-Scheduler-macOS-arm64-v0.3.0.dmg
AI-Usage-Window-Scheduler-macOS-arm64-v0.3.0.zip
SHA256SUMS.txt
```

The standalone bundle is CI-validated by running the frozen executable before the DMG is created. A tagged release (`v*`) automatically publishes the files to GitHub Releases.

The current build is ad-hoc signed but not Apple-notarized yet. Until a Developer ID certificate is configured, macOS may require **Control-click / right-click → Open** the first time. No Terminal command is required.

## Menu-bar dashboard

The menu bar displays usage/reset information from every provider that has data available.

Example:

```text
AI 68%

Claude · 41% used · reset 3h 12m
  5h · 24% used · reset 17:00
  7d · 41% used · reset Sun 14:00

ChatGPT · 68% used · reset 2d 3h
Grok · 32% used · reset 5h
Gemini · usage n/a

Claude wake · daily 05:00
Change wake time…
```

The dashboard layer is provider-agnostic. Claude, Grok, ChatGPT, Gemini, Perplexity, Copilot, Cursor, or future AI providers can all use the same usage/reset record model.

## Provider support

| Provider | Automated wake | Usage/reset dashboard | Automatic usage source |
|---|---:|---:|---:|
| Claude | ✅ verified adapter | ✅ | ✅ Claude Code status-line `rate_limits` |
| Grok | not enabled yet | ✅ | adapter pending a stable source |
| ChatGPT | not enabled yet | ✅ | adapter pending a stable source |
| Gemini | not enabled yet | ✅ | adapter pending a stable source |
| Any custom AI | provider-specific | ✅ | generic ingest/manual source |

The project deliberately does not harvest browser cookies, passwords, session tokens, or private browser profiles.

## Claude usage capture

Claude Code exposes subscriber rate-limit information to custom status-line commands. AI Window can ingest:

- five-hour used percentage;
- five-hour reset time;
- seven-day used percentage;
- seven-day reset time.

The universal widget then displays those values alongside other AI providers.

## Development installer

Before the first public DMG release, the development branch can still be installed with:

```bash
AI_WINDOW_REF=ai-window-v0.1.0 \
  curl -fsSL https://raw.githubusercontent.com/sparkfang-hub/ai-usage-window-scheduler/ai-window-v0.1.0/scripts/install_simple.sh | bash
```

This path is only for development/testing; the packaged DMG is the intended normal-user distribution.

## Advanced CLI

The CLI remains available for developers and provider-adapter work, but it is no longer the intended normal-user setup path.

```text
ai-window dashboard
ai-window usage set <provider> ...
ai-window usage clear <provider> ...
ai-window ingest-claude-statusline
ai-window widget
ai-window install-widget
ai-window setup <provider> ...
ai-window wake <provider>
ai-window test <provider>
ai-window status
ai-window doctor [provider]
```

Only use `ai-window test claude` when you intentionally want to make an immediate Claude request, because the test itself may start a usage window.

## Release engineering

`./scripts/build_macos_app.sh` creates the standalone `.app`, `.zip`, `.dmg`, and SHA-256 checksums. `.github/workflows/release-macos.yml` runs the same build on an Apple Silicon macOS runner and publishes tagged versions.

A future release can replace ad-hoc signing with Developer ID signing + Apple notarization without changing the app architecture.

## Design rules

1. **No quota bypassing.** The scheduler only sends ordinary provider requests.
2. **No credential harvesting.** No provider passwords, cookies, browser sessions, or API keys are collected by the scheduler.
3. **Provider-specific truth.** Each AI provider can use different quota semantics.
4. **Universal display, conservative automation.** Any provider can appear in the dashboard; automated retrieval/wake behavior is enabled only after it is verified.
5. **Local-first.** Configuration and usage snapshots stay on the user's Mac.

## Development

```bash
python -m unittest discover -s tests -v
```

## License

MIT
