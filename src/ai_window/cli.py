from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ai_window import __version__

APP_NAME = "ai-window"
DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_ALIASES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}
PROVIDERS = ("claude", "grok", "chatgpt", "gemini")


@dataclass
class WeeklyReset:
    weekday: int
    time: str


@dataclass
class ProviderConfig:
    enabled: bool = True
    work_start: str = "09:00"
    lead_minutes: int = 120
    days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    window_minutes: int = 0
    model: str | None = None
    weekly_resets: dict[str, WeeklyReset] = field(default_factory=dict)


@dataclass
class AppConfig:
    version: int = 1
    providers: dict[str, ProviderConfig] = field(default_factory=dict)


def config_dir() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()
    return root / APP_NAME


def state_dir() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")).expanduser()
    return root / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def state_path() -> Path:
    return state_dir() / "state.json"


def log_path() -> Path:
    return state_dir() / "ai-window.log"


def parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hour_s, minute_s = value.strip().split(":", 1)
        hour, minute = int(hour_s), int(minute_s)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Time must use HH:MM, for example 09:00") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Time must use a valid 24-hour HH:MM value")
    return hour, minute


def wake_time(work_start: str, lead_minutes: int) -> str:
    hour, minute = parse_hhmm(work_start)
    total = (hour * 60 + minute - lead_minutes) % 1440
    return f"{total // 60:02d}:{total % 60:02d}"


def parse_days(value: str) -> list[int]:
    text = value.strip().lower()
    if text in {"weekday", "weekdays"}:
        return [0, 1, 2, 3, 4]
    if text in {"daily", "everyday", "all"}:
        return list(range(7))
    days: list[int] = []
    for item in text.split(","):
        key = item.strip()
        if key not in DAY_ALIASES:
            raise ValueError(f"Unknown day: {item.strip()}")
        value_int = DAY_ALIASES[key]
        if value_int not in days:
            days.append(value_int)
    if not days:
        raise ValueError("At least one day is required")
    return sorted(days)


def format_days(days: list[int]) -> str:
    if days == [0, 1, 2, 3, 4]:
        return "weekdays"
    if days == list(range(7)):
        return "daily"
    return ",".join(DAY_NAMES[d] for d in sorted(days))


def next_occurrence(hhmm: str, days: list[int], now: datetime | None = None) -> datetime:
    now = now or datetime.now().astimezone()
    hour, minute = parse_hhmm(hhmm)
    for delta in range(8):
        date = (now + timedelta(days=delta)).date()
        if date.weekday() not in days:
            continue
        candidate = datetime.combine(date, datetime.min.time(), tzinfo=now.tzinfo).replace(hour=hour, minute=minute)
        if candidate > now:
            return candidate
    raise RuntimeError("Could not compute next occurrence")


def next_weekly_reset(reset: WeeklyReset, now: datetime | None = None) -> datetime:
    return next_occurrence(reset.time, [reset.weekday], now=now)


def launchd_weekday(py_weekday: int) -> int:
    # launchd: Sunday=0, Monday=1, ... Saturday=6
    return (py_weekday + 1) % 7


def _provider_from_dict(raw: dict[str, Any]) -> ProviderConfig:
    weekly = {name: WeeklyReset(**value) for name, value in (raw.get("weekly_resets") or {}).items()}
    return ProviderConfig(
        enabled=bool(raw.get("enabled", True)),
        work_start=str(raw.get("work_start", "09:00")),
        lead_minutes=int(raw.get("lead_minutes", 120)),
        days=[int(x) for x in raw.get("days", [0, 1, 2, 3, 4])],
        window_minutes=int(raw.get("window_minutes", 0)),
        model=raw.get("model"),
        weekly_resets=weekly,
    )


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig()
    raw = json.loads(path.read_text(encoding="utf-8"))
    providers = {name: _provider_from_dict(value) for name, value in (raw.get("providers") or {}).items()}
    return AppConfig(version=int(raw.get("version", 1)), providers=providers)


def save_config(config: AppConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {"version": 1, "providers": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_weekly(value: str) -> WeeklyReset:
    parts = value.strip().lower().split()
    if len(parts) != 2 or parts[0] not in DAY_ALIASES:
        raise ValueError("Weekly reset must look like: sun 14:00")
    parse_hhmm(parts[1])
    return WeeklyReset(weekday=DAY_ALIASES[parts[0]], time=parts[1])


def supports_wake(provider: str) -> bool:
    return provider == "claude"


def provider_doctor(provider: str) -> tuple[bool, str]:
    if provider != "claude":
        return True, "Tracking-only adapter; automated wake is not enabled"
    path = shutil.which("claude")
    if not path:
        return False, "Claude Code CLI not found in PATH"
    try:
        proc = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Claude CLI check failed: {exc}"
    version = (proc.stdout or proc.stderr).strip()
    if proc.returncode != 0:
        return False, f"Claude CLI returned exit code {proc.returncode}: {version}"
    return True, f"Claude Code CLI ready ({version or path})"


def claude_command(cfg: ProviderConfig) -> list[str]:
    return [
        shutil.which("claude") or "claude",
        "--bare",
        "-p",
        "SESSION_WAKE. Reply only with OK. Do not use tools.",
        "--model",
        cfg.model or "haiku",
        "--tools",
        "",
        "--disallowedTools",
        "mcp__*",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--output-format",
        "text",
        "--max-turns",
        "1",
    ]


def provider_wake(provider: str, cfg: ProviderConfig, dry_run: bool = False) -> tuple[bool, str, str]:
    if provider != "claude":
        return False, f"{provider} is tracking-only in v0.1; no verified wake rule is enabled", ""
    cmd = claude_command(cfg)
    if dry_run:
        printable = " ".join("''" if part == "" else part for part in cmd)
        return True, f"Dry run: {printable}", ""
    ok, message = provider_doctor(provider)
    if not ok:
        return False, message, ""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    except subprocess.TimeoutExpired:
        return False, "Claude wake timed out after 90 seconds", ""
    except OSError as exc:
        return False, f"Claude wake failed: {exc}", ""
    output = (proc.stdout or "").strip()
    if proc.returncode != 0:
        detail = (proc.stderr or output or "no output").strip()
        return False, f"Claude exited with code {proc.returncode}: {detail}", output
    return True, "Wake request completed", output


def plist_path(provider: str) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"com.aiwindow.{provider}.plist"


def build_plist(provider: str, cfg: ProviderConfig) -> dict[str, Any]:
    hhmm = wake_time(cfg.work_start, cfg.lead_minutes)
    hour, minute = parse_hhmm(hhmm)
    intervals = [
        {"Weekday": launchd_weekday(day), "Hour": hour, "Minute": minute}
        for day in cfg.days
    ]
    path_env = os.environ.get("PATH", "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    return {
        "Label": f"com.aiwindow.{provider}",
        "ProgramArguments": [sys.executable, "-m", "ai_window", "wake", provider, "--scheduled"],
        "StartCalendarInterval": intervals,
        "RunAtLoad": False,
        "StandardOutPath": str(log_path()),
        "StandardErrorPath": str(log_path()),
        "ProcessType": "Background",
        "EnvironmentVariables": {"HOME": str(Path.home()), "PATH": path_env},
    }


def install_schedule(provider: str, cfg: ProviderConfig) -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "Automatic scheduling currently supports macOS launchd only"
    if not supports_wake(provider):
        return False, f"{provider} does not have a verified wake adapter yet"
    path = plist_path(provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    log_path().parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump(build_plist(provider, cfg), fh, sort_keys=False)
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(path)], capture_output=True, check=False)
    proc = subprocess.run(["launchctl", "bootstrap", domain, str(path)], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return False, f"launchctl bootstrap failed: {(proc.stderr or proc.stdout).strip()}"
    subprocess.run(["launchctl", "enable", f"{domain}/com.aiwindow.{provider}"], capture_output=True, check=False)
    return True, f"Installed {path}"


def uninstall_schedule(provider: str) -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "Automatic scheduling currently supports macOS launchd only"
    path = plist_path(provider)
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(path)], capture_output=True, check=False)
    if path.exists():
        path.unlink()
    return True, f"Removed {path}"


def get_provider_cfg(config: AppConfig, provider: str) -> ProviderConfig:
    if provider not in config.providers:
        raise KeyError(f"{provider} is not configured. Run: ai-window setup {provider}")
    return config.providers[provider]


def cmd_setup(args: argparse.Namespace) -> int:
    config = load_config()
    old = config.providers.get(args.provider, ProviderConfig())
    work_start = args.work_start or old.work_start
    parse_hhmm(work_start)
    lead = args.lead_minutes if args.lead_minutes is not None else old.lead_minutes
    if not 0 <= lead < 1440:
        raise ValueError("Lead time must be between 0 and 1439 minutes")
    days = parse_days(args.days) if args.days else old.days
    weekly = dict(old.weekly_resets)
    if args.weekly_all:
        weekly["all_models"] = parse_weekly(args.weekly_all)
    if args.weekly_sonnet:
        weekly["sonnet"] = parse_weekly(args.weekly_sonnet)
    cfg = ProviderConfig(
        enabled=True,
        work_start=work_start,
        lead_minutes=lead,
        days=days,
        window_minutes=300 if args.provider == "claude" else 0,
        model=args.model or old.model or ("haiku" if args.provider == "claude" else None),
        weekly_resets=weekly,
    )
    config.providers[args.provider] = cfg
    path = save_config(config)
    print(f"Configured {args.provider}")
    print(f"  Work starts : {cfg.work_start}")
    print(f"  Wake time   : {wake_time(cfg.work_start, cfg.lead_minutes)} ({cfg.lead_minutes} min early)")
    print(f"  Days        : {format_days(cfg.days)}")
    if cfg.model:
        print(f"  Wake model  : {cfg.model}")
    print(f"  Config      : {path}")
    print(f"  Wake support: {'yes' if supports_wake(args.provider) else 'tracking only'}")
    if args.install:
        ok, message = install_schedule(args.provider, cfg)
        print(f"  Schedule    : {message}")
        return 0 if ok else 1
    return 0


def cmd_wake(args: argparse.Namespace) -> int:
    config = load_config()
    cfg = get_provider_cfg(config, args.provider)
    ok, message, output = provider_wake(args.provider, cfg, dry_run=args.dry_run)
    if not args.dry_run:
        state = load_state()
        providers = state.setdefault("providers", {})
        previous = providers.get(args.provider, {})
        entry = {
            "last_attempt": datetime.now().astimezone().isoformat(),
            "last_wake_ok": ok,
            "last_output": output[:500],
            "last_message": message[:1000],
            "scheduled": bool(getattr(args, "scheduled", False)),
        }
        if ok:
            entry["last_successful_wake"] = datetime.now().astimezone().isoformat()
        elif previous.get("last_successful_wake"):
            entry["last_successful_wake"] = previous["last_successful_wake"]
        providers[args.provider] = entry
        save_state(state)
    print(f"[{'OK' if ok else 'ERROR'}] {args.provider}: {message}")
    if output:
        print(output)
    return 0 if ok else 1


def cmd_status(args: argparse.Namespace) -> int:
    config = load_config()
    state = load_state()
    if not config.providers:
        print("No providers configured. Example: ai-window setup claude --work-start 09:00 --lead-minutes 120 --install")
        return 0
    now = datetime.now().astimezone()
    print("AI Usage Window Scheduler")
    print(f"Now: {now.strftime('%a %Y-%m-%d %H:%M %Z')}")
    for name, cfg in sorted(config.providers.items()):
        wake = wake_time(cfg.work_start, cfg.lead_minutes)
        print(f"\n{name.upper()}")
        print(f"  Schedule        : {format_days(cfg.days)} at {wake}")
        print(f"  Work start      : {cfg.work_start}")
        print(f"  Next wake       : {next_occurrence(wake, cfg.days, now).strftime('%a %Y-%m-%d %H:%M %Z')}")
        entry = state.get("providers", {}).get(name, {})
        last_success = entry.get("last_successful_wake")
        if last_success:
            dt = datetime.fromisoformat(last_success)
            print(f"  Last local wake : {dt.strftime('%a %Y-%m-%d %H:%M %Z')}")
            if cfg.window_minutes:
                reset = dt + timedelta(minutes=cfg.window_minutes)
                label = reset.strftime('%a %Y-%m-%d %H:%M %Z')
                print(f"  Est. reset      : {label if reset > now else 'elapsed (' + label + ')'}")
        else:
            print("  Last local wake : none")
        for scope, reset in cfg.weekly_resets.items():
            nxt = next_weekly_reset(reset, now)
            print(f"  Weekly {scope:10}: {nxt.strftime('%a %Y-%m-%d %H:%M %Z')}")
        if name == "claude":
            print("  Note            : Claude Settings > Usage is authoritative if Claude was used elsewhere.")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    names = [args.provider] if args.provider else list(PROVIDERS)
    failures = 0
    for name in names:
        ok, message = provider_doctor(name)
        print(f"{'OK' if ok else 'ERROR':5} {name:8} {message}")
        failures += 0 if ok else 1
    return 1 if failures else 0


def cmd_install(args: argparse.Namespace) -> int:
    cfg = get_provider_cfg(load_config(), args.provider)
    ok, message = install_schedule(args.provider, cfg)
    print(message)
    return 0 if ok else 1


def cmd_uninstall(args: argparse.Namespace) -> int:
    ok, message = uninstall_schedule(args.provider)
    print(message)
    return 0 if ok else 1


def cmd_config(args: argparse.Namespace) -> int:
    path = config_path()
    if args.path:
        print(path)
    elif not path.exists():
        print("{}")
    else:
        print(json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-window", description="Schedule and track AI usage reset windows")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="Configure a provider")
    setup.add_argument("provider", choices=PROVIDERS)
    setup.add_argument("--work-start", metavar="HH:MM")
    setup.add_argument("--lead-minutes", type=int)
    setup.add_argument("--days", help="weekdays, daily, or mon,tue,wed")
    setup.add_argument("--model", help="Claude wake defaults to haiku")
    setup.add_argument("--weekly-all", metavar="'SUN HH:MM'")
    setup.add_argument("--weekly-sonnet", metavar="'SUN HH:MM'")
    setup.add_argument("--install", action="store_true")
    setup.set_defaults(func=cmd_setup)

    wake = sub.add_parser("wake", help="Send one minimal wake request")
    wake.add_argument("provider", choices=PROVIDERS)
    wake.add_argument("--dry-run", action="store_true")
    wake.add_argument("--scheduled", action="store_true", help=argparse.SUPPRESS)
    wake.set_defaults(func=cmd_wake)

    test = sub.add_parser("test", help="Test a provider wake immediately")
    test.add_argument("provider", choices=PROVIDERS)
    test.add_argument("--dry-run", action="store_true")
    test.set_defaults(func=cmd_wake, scheduled=False)

    status = sub.add_parser("status", help="Show local schedule and estimated resets")
    status.set_defaults(func=cmd_status)

    doctor = sub.add_parser("doctor", help="Check provider prerequisites")
    doctor.add_argument("provider", nargs="?", choices=PROVIDERS)
    doctor.set_defaults(func=cmd_doctor)

    install = sub.add_parser("install-schedule")
    install.add_argument("provider", choices=PROVIDERS)
    install.set_defaults(func=cmd_install)

    uninstall = sub.add_parser("uninstall-schedule")
    uninstall.add_argument("provider", choices=PROVIDERS)
    uninstall.set_defaults(func=cmd_uninstall)

    show = sub.add_parser("config")
    show.add_argument("--path", action="store_true")
    show.set_defaults(func=cmd_config)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (ValueError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
