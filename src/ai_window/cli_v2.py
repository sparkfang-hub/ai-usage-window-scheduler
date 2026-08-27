from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ai_window.cli import load_config, load_state, log_path, save_state, state_dir
from ai_window.cli import main as legacy_main
from ai_window.usage import (
    build_usage_snapshot,
    format_countdown,
    format_usage_record,
    normalize_provider,
    parse_percent,
    parse_reset_at,
    provider_display_name,
)

NEW_COMMANDS = {
    "dashboard",
    "usage",
    "ingest-claude-statusline",
    "widget",
    "install-widget",
    "uninstall-widget",
}


def _usage_store(state: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("usage", {})
    return state["usage"]


def _print_dashboard(provider_filter: str | None = None) -> int:
    config = load_config()
    state = load_state()
    now = datetime.now().astimezone()
    rows = build_usage_snapshot(config, state, now)
    if provider_filter:
        wanted = normalize_provider(provider_filter)
        rows = [row for row in rows if row["provider"] == wanted]

    print("AI Usage Dashboard")
    print(f"Now: {now.strftime('%a %Y-%m-%d %H:%M %Z')}")
    if not rows:
        print("No matching provider usage data.")
        return 0

    for row in rows:
        print(f"\n{row['display_name'].upper()}")
        if not row["records"]:
            print("  no usage data yet")
            continue
        for record in row["records"]:
            print("  " + format_usage_record(record, now))
            source = record.get("source") or "unknown"
            print(f"    source: {source}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    return _print_dashboard(args.provider)


def cmd_usage_set(args: argparse.Namespace) -> int:
    provider = normalize_provider(args.provider)
    scope = args.scope.strip() or "primary"
    if args.used is None and args.remaining is None:
        raise ValueError("Provide --used or --remaining")
    if args.used is not None and args.remaining is not None:
        raise ValueError("Use only one of --used or --remaining")

    used = parse_percent(args.used) if args.used is not None else round(100.0 - parse_percent(args.remaining), 2)
    remaining = round(100.0 - used, 2)
    now = datetime.now().astimezone()

    reset_dt = None
    if args.reset_at and args.reset_in_minutes is not None:
        raise ValueError("Use only one of --reset-at or --reset-in-minutes")
    if args.reset_at:
        reset_dt = parse_reset_at(args.reset_at, now)
    elif args.reset_in_minutes is not None:
        if args.reset_in_minutes < 0:
            raise ValueError("--reset-in-minutes must be zero or greater")
        reset_dt = now + timedelta(minutes=args.reset_in_minutes)

    state = load_state()
    store = _usage_store(state)
    provider_store = store.setdefault(provider, {})
    provider_store[scope] = {
        "scope": scope,
        "used_percent": used,
        "remaining_percent": remaining,
        "reset_at": reset_dt.isoformat() if reset_dt else None,
        "source": args.source,
        "updated_at": now.isoformat(),
        "note": args.note,
    }
    save_state(state)
    print(f"Saved {provider_display_name(provider)} / {scope}: {used:.1f}% used")
    if reset_dt:
        print(f"Reset: {reset_dt.strftime('%a %Y-%m-%d %H:%M %Z')} ({format_countdown(reset_dt, now)})")
    return 0


def cmd_usage_clear(args: argparse.Namespace) -> int:
    provider = normalize_provider(args.provider)
    state = load_state()
    store = _usage_store(state)
    if provider not in store:
        print(f"No stored usage for {provider}")
        return 0
    if args.scope:
        store[provider].pop(args.scope, None)
        if not store[provider]:
            store.pop(provider, None)
    else:
        store.pop(provider, None)
    save_state(state)
    print(f"Cleared stored usage for {provider}" + (f" / {args.scope}" if args.scope else ""))
    return 0


def cmd_usage_show(args: argparse.Namespace) -> int:
    return _print_dashboard(args.provider)


def _timestamp_to_datetime(value: Any, now: datetime) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=now.tzinfo).astimezone()
    if isinstance(value, str):
        try:
            return parse_reset_at(value, now)
        except ValueError:
            try:
                return datetime.fromtimestamp(float(value), tz=now.tzinfo).astimezone()
            except ValueError:
                return None
    return None


def cmd_ingest_claude_statusline(args: argparse.Namespace) -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Claude status-line JSON: {exc}") from exc

    limits = payload.get("rate_limits") or {}
    mapping = {"five_hour": "5h", "seven_day": "7d"}
    now = datetime.now().astimezone()
    state = load_state()
    provider_store = _usage_store(state).setdefault("claude", {})
    captured = 0

    for source_key, scope in mapping.items():
        raw = limits.get(source_key)
        if not isinstance(raw, dict):
            continue
        used_raw = raw.get("used_percentage")
        used = parse_percent(used_raw) if used_raw is not None else None
        reset_dt = _timestamp_to_datetime(raw.get("resets_at"), now)
        provider_store[scope] = {
            "scope": scope,
            "used_percent": used,
            "remaining_percent": round(100.0 - used, 2) if used is not None else None,
            "reset_at": reset_dt.isoformat() if reset_dt else None,
            "source": "claude-statusline",
            "updated_at": now.isoformat(),
            "note": "Captured from Claude Code rate_limits status-line JSON.",
        }
        captured += 1

    save_state(state)

    # A status-line command should always emit a compact, useful line.
    snapshot = build_usage_snapshot(load_config(), state, now)
    claude = next((row for row in snapshot if row["provider"] == "claude"), None)
    pieces: list[str] = []
    if claude:
        for rec in claude["records"]:
            if rec.get("source") != "claude-statusline":
                continue
            text = str(rec.get("scope", "limit"))
            if rec.get("used_percent") is not None:
                text += f" {float(rec['used_percent']):.0f}%"
            if rec.get("reset_dt"):
                text += f" ↻{format_countdown(rec['reset_dt'], now)}"
            pieces.append(text)
    print("AI Window | " + " | ".join(pieces) if pieces else "AI Window")
    return 0 if captured or not limits else 1


def widget_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / "com.aiwindow.widget.plist"


def build_widget_plist() -> dict[str, Any]:
    path_env = os.environ.get("PATH", "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    return {
        "Label": "com.aiwindow.widget",
        "ProgramArguments": [sys.executable, "-m", "ai_window", "widget", "--run"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Interactive",
        "StandardOutPath": str(log_path()),
        "StandardErrorPath": str(log_path()),
        "EnvironmentVariables": {"HOME": str(Path.home()), "PATH": path_env},
    }


def install_widget() -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "The menu-bar widget currently supports macOS only"
    try:
        import rumps  # noqa: F401
    except ImportError:
        return False, "rumps is missing. Reinstall with the [widget] extra."
    path = widget_plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state_dir().mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump(build_widget_plist(), fh, sort_keys=False)
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(path)], capture_output=True, check=False)
    proc = subprocess.run(["launchctl", "bootstrap", domain, str(path)], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return False, f"launchctl bootstrap failed: {(proc.stderr or proc.stdout).strip()}"
    return True, f"Installed menu-bar widget: {path}"


def uninstall_widget() -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "The menu-bar widget currently supports macOS only"
    path = widget_plist_path()
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(path)], capture_output=True, check=False)
    if path.exists():
        path.unlink()
    return True, f"Removed menu-bar widget: {path}"


def cmd_widget(args: argparse.Namespace) -> int:
    from ai_window.widget import run_widget
    return run_widget()


def cmd_install_widget(args: argparse.Namespace) -> int:
    ok, message = install_widget()
    print(message)
    return 0 if ok else 1


def cmd_uninstall_widget(args: argparse.Namespace) -> int:
    ok, message = uninstall_widget()
    print(message)
    return 0 if ok else 1


def build_new_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-window", description="Universal AI usage/reset dashboard")
    sub = parser.add_subparsers(dest="command", required=True)

    dashboard = sub.add_parser("dashboard", help="Show usage and reset times for AI providers")
    dashboard.add_argument("--provider")
    dashboard.set_defaults(func=cmd_dashboard)

    usage = sub.add_parser("usage", help="Store or display provider usage data")
    usage_sub = usage.add_subparsers(dest="usage_command", required=True)

    usage_set = usage_sub.add_parser("set", help="Set usage/reset data for any provider")
    usage_set.add_argument("provider")
    usage_set.add_argument("--scope", default="primary")
    usage_set.add_argument("--used", type=float)
    usage_set.add_argument("--remaining", type=float)
    usage_set.add_argument("--reset-at")
    usage_set.add_argument("--reset-in-minutes", type=int)
    usage_set.add_argument("--source", default="manual")
    usage_set.add_argument("--note")
    usage_set.set_defaults(func=cmd_usage_set)

    usage_clear = usage_sub.add_parser("clear", help="Clear stored provider usage")
    usage_clear.add_argument("provider")
    usage_clear.add_argument("--scope")
    usage_clear.set_defaults(func=cmd_usage_clear)

    usage_show = usage_sub.add_parser("show", help="Show stored/derived usage and reset data")
    usage_show.add_argument("--provider")
    usage_show.set_defaults(func=cmd_usage_show)

    ingest = sub.add_parser("ingest-claude-statusline", help="Capture Claude Code rate_limits JSON from stdin")
    ingest.set_defaults(func=cmd_ingest_claude_statusline)

    widget = sub.add_parser("widget", help="Run the macOS menu-bar usage widget")
    widget.add_argument("--run", action="store_true", help=argparse.SUPPRESS)
    widget.set_defaults(func=cmd_widget)

    install_widget_parser = sub.add_parser("install-widget", help="Start the menu-bar widget at login")
    install_widget_parser.set_defaults(func=cmd_install_widget)

    uninstall_widget_parser = sub.add_parser("uninstall-widget", help="Remove the menu-bar widget LaunchAgent")
    uninstall_widget_parser.set_defaults(func=cmd_uninstall_widget)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in NEW_COMMANDS:
        return legacy_main(argv)
    args = build_new_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
