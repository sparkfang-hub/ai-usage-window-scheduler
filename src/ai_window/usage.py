from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

DISPLAY_NAMES = {
    "claude": "Claude",
    "grok": "Grok",
    "chatgpt": "ChatGPT",
    "gemini": "Gemini",
}


def provider_display_name(provider: str) -> str:
    key = provider.strip().lower()
    return DISPLAY_NAMES.get(key, key.replace("_", " ").replace("-", " ").title())


def normalize_provider(provider: str) -> str:
    value = provider.strip().lower().replace(" ", "-")
    if not value or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-_." for ch in value):
        raise ValueError("Provider must contain only letters, digits, '-', '_' or '.'")
    return value


def parse_percent(value: float | int | str) -> float:
    pct = float(value)
    if not 0 <= pct <= 100:
        raise ValueError("Usage percentage must be between 0 and 100")
    return round(pct, 2)


def parse_reset_at(value: str, now: datetime | None = None) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("Reset time must be ISO-8601, for example 2026-08-21T17:00:00+08:00") from exc
    now = now or datetime.now().astimezone()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=now.tzinfo)
    return dt.astimezone()


def format_countdown(target: datetime | None, now: datetime | None = None) -> str:
    if target is None:
        return "unknown"
    now = now or datetime.now().astimezone()
    seconds = int((target - now).total_seconds())
    if seconds <= 0:
        return "elapsed"
    minutes = (seconds + 59) // 60
    days, rem = divmod(minutes, 1440)
    hours, mins = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def usage_bar(used_percent: float | None, width: int = 10) -> str:
    if used_percent is None:
        return "[" + "-" * width + "]"
    filled = max(0, min(width, round(width * used_percent / 100)))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _record_reset(record: dict[str, Any]) -> datetime | None:
    raw = record.get("reset_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw)).astimezone()
    except (ValueError, TypeError):
        return None


def build_usage_snapshot(config: Any, state: dict[str, Any], now: datetime | None = None) -> list[dict[str, Any]]:
    """Build provider-agnostic usage/reset rows for CLI and menu-bar widget.

    Manual or collector-fed data lives under state['usage'][provider][scope].
    Claude/local schedule-derived reset times are merged without pretending to
    know a percentage when the provider did not expose one.
    """
    now = now or datetime.now().astimezone()
    usage_state = state.get("usage", {}) if isinstance(state, dict) else {}
    provider_names = {"claude", "grok", "chatgpt", "gemini"}
    provider_names.update(getattr(config, "providers", {}).keys())
    provider_names.update(usage_state.keys())

    rows: list[dict[str, Any]] = []
    wake_state = state.get("providers", {}) if isinstance(state, dict) else {}

    for provider in sorted(provider_names):
        records: dict[str, dict[str, Any]] = {}
        for scope, raw in (usage_state.get(provider, {}) or {}).items():
            record = dict(raw)
            record.setdefault("scope", scope)
            record.setdefault("source", "manual")
            record["reset_dt"] = _record_reset(record)
            records[scope] = record

        cfg = getattr(config, "providers", {}).get(provider)
        if cfg is not None:
            last_success = (wake_state.get(provider, {}) or {}).get("last_successful_wake")
            if last_success and getattr(cfg, "window_minutes", 0):
                try:
                    start = datetime.fromisoformat(last_success).astimezone()
                    reset_dt = start + timedelta(minutes=int(cfg.window_minutes))
                    records.setdefault(
                        "session",
                        {
                            "scope": "session",
                            "used_percent": None,
                            "remaining_percent": None,
                            "reset_at": reset_dt.isoformat(),
                            "reset_dt": reset_dt,
                            "source": "derived-local-wake",
                            "updated_at": last_success,
                            "note": "Reset estimate from the last local wake. Provider UI remains authoritative.",
                        },
                    )
                except (ValueError, TypeError):
                    pass

            for scope, weekly in getattr(cfg, "weekly_resets", {}).items():
                weekday = int(weekly.weekday)
                hour, minute = map(int, str(weekly.time).split(":"))
                days_ahead = (weekday - now.weekday()) % 7
                reset_dt = (now + timedelta(days=days_ahead)).replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                if reset_dt <= now:
                    reset_dt += timedelta(days=7)
                key = f"weekly:{scope}"
                records.setdefault(
                    key,
                    {
                        "scope": key,
                        "used_percent": None,
                        "remaining_percent": None,
                        "reset_at": reset_dt.isoformat(),
                        "reset_dt": reset_dt,
                        "source": "configured-weekly-reset",
                        "updated_at": None,
                    },
                )

        record_list = list(records.values())
        record_list.sort(key=lambda rec: rec.get("reset_dt").timestamp() if rec.get("reset_dt") is not None else float("inf"))
        used_values = [float(r["used_percent"]) for r in record_list if r.get("used_percent") is not None]
        reset_values = [r.get("reset_dt") for r in record_list if r.get("reset_dt") and r.get("reset_dt") > now]
        rows.append(
            {
                "provider": provider,
                "display_name": provider_display_name(provider),
                "records": record_list,
                "max_used_percent": max(used_values) if used_values else None,
                "next_reset": min(reset_values) if reset_values else None,
            }
        )
    return rows


def format_usage_record(record: dict[str, Any], now: datetime | None = None) -> str:
    now = now or datetime.now().astimezone()
    used = record.get("used_percent")
    bar = usage_bar(float(used) if used is not None else None)
    usage_text = f"{float(used):5.1f}% used" if used is not None else "  n/a usage"
    reset_dt = record.get("reset_dt")
    reset_text = "reset unknown"
    if reset_dt:
        reset_text = f"reset {format_countdown(reset_dt, now)} ({reset_dt.strftime('%a %H:%M')})"
    return f"{record.get('scope', 'primary'):<18} {bar} {usage_text}  {reset_text}"
