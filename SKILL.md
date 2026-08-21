---
name: ai-usage-window-scheduler
description: Configure, inspect, and optimize AI usage windows. Use when a user wants to schedule an intentionally tiny provider request before their normal work time, track fixed weekly resets, inspect the next scheduled wake, or manage the local macOS schedule. Never claim a provider supports a wake-triggered rolling window unless its adapter explicitly declares that capability.
---

# AI Usage Window Scheduler

Use the `ai-window` CLI as the source of truth for local configuration.

## Core rules

1. Treat provider rules as provider-specific. Do not assume all AI services use Claude-style rolling sessions.
2. A wake request is an ordinary minimal request, not a bypass of a usage limit.
3. For Claude, prefer the minimal Haiku wake implemented by the adapter. The adapter disables tools, MCP access, skills/commands, and conversation persistence.
4. Weekly reset tracking is informational. A fixed weekly reset is not "started" by the wake request.
5. Local reset times are estimates when the user may have used the provider elsewhere. For Claude, Settings > Usage is authoritative.
6. Never store passwords, cookies, session tokens, or API keys in this skill's configuration.

## Common actions

- Configure Claude: `ai-window setup claude --work-start 09:00 --lead-minutes 120 --days weekdays --install`
- Test immediately: `ai-window test claude`
- Check prerequisites: `ai-window doctor claude`
- Inspect schedule: `ai-window status`
- Remove schedule: `ai-window uninstall-schedule claude`

## Provider capability model

- `claude`: rolling five-hour session wake supported; weekly reset tracking supported.
- `grok`: tracking-only until a verified compatible trigger exists.
- `chatgpt`: tracking-only placeholder until a verified compatible trigger exists.
- `gemini`: tracking-only placeholder until a verified compatible trigger exists.

When provider policies change, update only the relevant adapter and documentation rather than hard-coding one provider's reset semantics into the scheduler core.
