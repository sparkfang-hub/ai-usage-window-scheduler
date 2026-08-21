---
name: ai-usage-window-scheduler
description: Configure and inspect AI provider usage windows, usage percentages, reset times, and macOS menu-bar monitoring. Claude can also use a verified minimal wake schedule and Claude Code rate-limit status-line ingestion.
---

# AI Usage Window Scheduler

Use this skill when a user wants to coordinate AI usage/reset windows, see quota usage in one place, configure a provider schedule, or run the local menu-bar monitor.

## Core principles

- Never describe the tool as bypassing or increasing a provider's quota.
- Treat each provider's current UI/documentation as authoritative.
- Never request or store passwords, cookies, session tokens, or browser profiles.
- The dashboard accepts arbitrary provider names; automation remains provider-specific.
- If a provider does not expose a verified machine-readable usage source, use the universal manual/ingest interface rather than scraping private web state.

## Common actions

### Show all AI usage/reset windows

```bash
ai-window dashboard
```

### Record usage for any provider

```bash
ai-window usage set <provider> --scope <scope> --used <0-100> --reset-in-minutes <minutes>
```

or:

```bash
ai-window usage set <provider> --scope <scope> --remaining <0-100> --reset-at <ISO-8601>
```

### Run the macOS menu-bar widget

```bash
ai-window install-widget
```

The widget refreshes local usage/reset state every 60 seconds.

### Claude automatic usage capture

Claude Code can send its official status-line JSON to:

```bash
ai-window ingest-claude-statusline
```

The command captures Claude subscriber `five_hour` and `seven_day` rate-limit percentage/reset fields and prints a compact status line. If the user already has a custom status line, tell them to compose/wrap rather than blindly replace it.

### Claude daily 05:00 wake

```bash
ai-window setup claude --work-start 05:00 --lead-minutes 0 --days daily --install
```

Only run `ai-window test claude` when the user intentionally wants an immediate request; testing can itself start a provider usage window.

## Provider support model

- Claude: verified wake adapter; automatic rate-limit ingestion from Claude Code status-line JSON.
- Grok / ChatGPT / Gemini: universal dashboard works; do not claim automatic quota retrieval until a stable verified source is implemented.
- Any additional AI: supported by the universal usage state model via `ai-window usage set` or future collector adapters.
