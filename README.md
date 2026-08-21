# AI Usage Window Scheduler

**Wake the AI before you need the AI.**

AI Usage Window Scheduler (`ai-window`) is a small macOS-first utility for planning provider usage windows. Its first working provider is Claude: it can schedule a deliberately tiny Claude Code request before your normal work time, record the local wake time, estimate the five-hour reset, and track fixed weekly reset times you enter from Claude's **Settings > Usage** page.

> This project does not bypass provider limits. It schedules ordinary requests and tracks published reset behavior. Provider rules can change, so the provider's own Usage page remains authoritative.

## Why

If you normally start heavy Claude work at 09:00 and choose a two-hour lead, `ai-window` can run a tiny wake at 07:00. On macOS it uses your own `launchd` LaunchAgent, so no cloud server, password, cookie, or API key is stored by this project.

## Provider status

| Provider | Automated wake | Local window estimate | Weekly reset tracking |
|---|---:|---:|---:|
| Claude | ✅ | ✅ five-hour window | ✅ manual reset time |
| Grok | — | — | adapter reserved |
| ChatGPT | — | — | adapter reserved |
| Gemini | — | — | adapter reserved |

Adapters are intentionally conservative: a service is not marked wake-capable until its current behavior has been verified.

## Requirements

- macOS for automatic scheduling (`launchd`)
- Python 3.10+
- Claude Code CLI installed and logged in for Claude wake requests

## Install

After a release is merged to `main`:

```bash
curl -fsSL https://raw.githubusercontent.com/sparkfang-hub/ai-usage-window-scheduler/main/scripts/install.sh | bash
```

For a development branch, set `AI_WINDOW_REF` before running the matching raw installer.

Make sure `~/.local/bin` is on your PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## 60-second setup

Check Claude Code:

```bash
ai-window doctor claude
```

Configure a 09:00 work start, wake Claude 120 minutes earlier on weekdays, and install the Mac schedule:

```bash
ai-window setup claude \
  --work-start 09:00 \
  --lead-minutes 120 \
  --days weekdays \
  --install
```

Test the tiny request immediately:

```bash
ai-window test claude
```

Then check **Claude > Settings > Usage** to verify that the session timing behaves as expected for your account.

Inspect your local schedule:

```bash
ai-window status
```

## Weekly reset tracking

Claude weekly limits reset at a fixed account-assigned time; they are not started by the wake request. Copy the reset time shown in Claude Settings > Usage into the scheduler, for example:

```bash
ai-window setup claude \
  --weekly-all "sun 14:00" \
  --weekly-sonnet "sun 14:00"
```

Then `ai-window status` shows the next occurrence. Use the actual day/time shown on your account rather than this example.

## What the Claude wake actually runs

The Claude adapter uses Claude Code's non-interactive print mode with a tiny prompt and conservative flags:

- `--bare` to skip project/skill/plugin/MCP auto-discovery
- `--model haiku`
- `--tools ""` and MCP denial so it cannot operate on files or run commands
- `--disable-slash-commands`
- `--no-session-persistence`
- one agentic turn

The prompt asks only for `OK`.

## Commands

```text
ai-window setup <provider>        Configure work time, lead time, days and weekly resets
ai-window doctor [provider]       Check local prerequisites
ai-window wake <provider>         Run one minimal wake
ai-window test <provider>         Test a wake immediately
ai-window status                  Show next wake and local reset estimates
ai-window install-schedule <p>    Install/update macOS LaunchAgent
ai-window uninstall-schedule <p>  Remove macOS LaunchAgent
ai-window config                  Show saved config
```

## Files created on your Mac

```text
~/.config/ai-window/config.json
~/.local/state/ai-window/state.json
~/.local/state/ai-window/ai-window.log
~/Library/LaunchAgents/com.aiwindow.claude.plist
```

No account credentials are stored by AI Usage Window Scheduler.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests -v
```

## License

MIT
