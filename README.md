# AI Usage Window Scheduler

**Wake the AI before you need the AI — and keep every provider's usage/reset window visible.**

AI Usage Window Scheduler (`ai-window`) is a macOS-first utility for:

- scheduling verified provider wake requests when a provider's limit window is first-use based;
- tracking usage percentage and reset time across AI providers;
- showing the data in one CLI dashboard;
- showing the same data in a small macOS menu-bar widget;
- accepting any provider name, not just Claude / Grok / ChatGPT / Gemini.

> This project does not bypass provider limits. It schedules ordinary requests and displays usage/reset data that the provider exposes or the user supplies. Provider rules and UIs remain authoritative.

## Provider model

| Provider | Automated wake | Usage/reset dashboard | Automatic usage source |
|---|---:|---:|---:|
| Claude | ✅ verified adapter | ✅ | ✅ Claude Code status-line `rate_limits` |
| Grok | not enabled | ✅ | adapter can be added when a stable source is available |
| ChatGPT | not enabled | ✅ | adapter can be added when a stable source is available |
| Gemini | not enabled | ✅ | adapter can be added when a stable source is available |
| Any custom AI | provider-specific | ✅ | generic ingest/manual data works now |

The dashboard is provider-agnostic. A service is only marked auto-readable or wake-capable after its behavior/source is verified; the project does not scrape browser cookies or store provider passwords.

## Requirements

- macOS for `launchd` scheduling and the menu-bar widget
- Python 3.10+
- Claude Code CLI installed and logged in for Claude wake requests

## Install

After a release is merged to `main`:

```bash
curl -fsSL https://raw.githubusercontent.com/sparkfang-hub/ai-usage-window-scheduler/main/scripts/install.sh | bash
```

For the current development PR/branch:

```bash
AI_WINDOW_REF=ai-window-v0.1.0 \
  curl -fsSL https://raw.githubusercontent.com/sparkfang-hub/ai-usage-window-scheduler/ai-window-v0.1.0/scripts/install.sh | bash
```

Make sure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Universal usage + reset dashboard

Show all known/configured providers:

```bash
ai-window dashboard
```

Store usage for **any** provider, including providers not built into the project:

```bash
ai-window usage set chatgpt \
  --scope weekly \
  --used 68 \
  --reset-in-minutes 1440
```

```bash
ai-window usage set perplexity-ai \
  --scope primary \
  --remaining 42 \
  --reset-at 2026-08-22T09:00:00+08:00
```

Then:

```bash
ai-window dashboard
```

The state is kept locally under `~/.local/state/ai-window/`.

## macOS menu-bar widget

Install the widget as a login LaunchAgent:

```bash
ai-window install-widget
```

The menu bar shows a compact `AI <highest-used-%>` title. Open it to see each provider's usage, countdown, reset clock time, scope, and data source. It refreshes every 60 seconds.

Run it manually instead:

```bash
ai-window widget
```

Remove it:

```bash
ai-window uninstall-widget
```

## Claude: automatic 5-hour + 7-day usage capture

Claude Code officially exposes subscriber rate limits to custom status-line commands after the first API response. The JSON includes:

- `rate_limits.five_hour.used_percentage`
- `rate_limits.five_hour.resets_at`
- `rate_limits.seven_day.used_percentage`
- `rate_limits.seven_day.resets_at`

`ai-window` can consume that JSON directly:

```bash
ai-window ingest-claude-statusline
```

To use it as your Claude Code status line, configure Claude Code's status-line command to invoke `ai-window ingest-claude-statusline`. It stores the values locally and prints a compact line such as:

```text
AI Window | 5h 24% ↻3h 11m | 7d 41% ↻4d 9h
```

If you already use a custom Claude status line, do not overwrite it blindly; compose or wrap the commands instead.

## Claude wake scheduler

Check Claude Code:

```bash
ai-window doctor claude
```

Example: wake Claude every day at **05:00**, including weekends:

```bash
ai-window setup claude \
  --work-start 05:00 \
  --lead-minutes 0 \
  --days daily \
  --install
```

Inspect everything together:

```bash
ai-window status
```

Test one wake immediately only when you intentionally want to start a session window:

```bash
ai-window test claude
```

## Weekly reset tracking

Fixed weekly reset clocks can also be configured when a provider displays them:

```bash
ai-window setup claude --weekly-all "sun 14:00" --weekly-sonnet "sun 14:00"
```

These configured reset clocks are displayed but are not treated as wake-triggered windows.

## Commands

```text
ai-window setup <provider>
ai-window wake <provider>
ai-window test <provider>
ai-window status
ai-window dashboard [--provider <name>]
ai-window usage set <provider> ...
ai-window usage clear <provider> [--scope <scope>]
ai-window usage show [--provider <name>]
ai-window ingest-claude-statusline
ai-window widget
ai-window install-widget
ai-window uninstall-widget
ai-window doctor [provider]
ai-window install-schedule <provider>
ai-window uninstall-schedule <provider>
ai-window config
```

## Design rules

1. **No limit bypassing.** Ordinary provider requests only.
2. **No credential harvesting.** No passwords, cookies, session tokens, or browser-profile scraping.
3. **Provider-specific truth.** Different AI services have different quota semantics.
4. **Universal display, conservative automation.** Any provider can appear in the dashboard; automation is enabled only when verified.
5. **Local-first state.** Usage snapshots and schedule state stay on the user's machine.

## License

MIT
