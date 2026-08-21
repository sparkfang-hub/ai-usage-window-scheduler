from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Any

from ai_window.cli import ProviderConfig, log_path, parse_hhmm, state_dir, wake_time


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _runtime_args(*args: str) -> list[str]:
    if is_frozen():
        return [sys.executable, *args]
    return [sys.executable, "-m", "ai_window", *args]


def _path_env() -> str:
    home = str(Path.home())
    parts = [
        f"{home}/.local/bin",
        f"{home}/.npm-global/bin",
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    inherited = os.environ.get("PATH", "")
    if inherited:
        parts.append(inherited)
    return ":".join(parts)


def _bootstrap(label: str, path: Path) -> tuple[bool, str]:
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(path)], capture_output=True, check=False)
    proc = subprocess.run(
        ["launchctl", "bootstrap", domain, str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return False, f"launchctl bootstrap failed: {(proc.stderr or proc.stdout).strip()}"
    subprocess.run(["launchctl", "enable", f"{domain}/{label}"], capture_output=True, check=False)
    return True, f"Installed {path}"


def install_claude_schedule(cfg: ProviderConfig) -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "Automatic scheduling currently supports macOS only"

    hhmm = wake_time(cfg.work_start, cfg.lead_minutes)
    hour, minute = parse_hhmm(hhmm)
    # launchd Weekday: Sunday=0, Monday=1 ... Saturday=6.
    intervals = [
        {"Weekday": (day + 1) % 7, "Hour": hour, "Minute": minute}
        for day in cfg.days
    ]

    path = Path.home() / "Library" / "LaunchAgents" / "com.aiwindow.claude.plist"
    path.parent.mkdir(parents=True, exist_ok=True)
    state_dir().mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "Label": "com.aiwindow.claude",
        "ProgramArguments": _runtime_args("wake", "claude", "--scheduled"),
        "StartCalendarInterval": intervals,
        "RunAtLoad": False,
        "StandardOutPath": str(log_path()),
        "StandardErrorPath": str(log_path()),
        "ProcessType": "Background",
        "EnvironmentVariables": {"HOME": str(Path.home()), "PATH": _path_env()},
    }
    with path.open("wb") as fh:
        plistlib.dump(data, fh, sort_keys=False)
    return _bootstrap("com.aiwindow.claude", path)


def install_widget_agent() -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "The menu-bar widget currently supports macOS only"

    path = Path.home() / "Library" / "LaunchAgents" / "com.aiwindow.widget.plist"
    path.parent.mkdir(parents=True, exist_ok=True)
    state_dir().mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "Label": "com.aiwindow.widget",
        "ProgramArguments": _runtime_args("widget", "--run"),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Interactive",
        "StandardOutPath": str(log_path()),
        "StandardErrorPath": str(log_path()),
        "EnvironmentVariables": {"HOME": str(Path.home()), "PATH": _path_env()},
    }
    with path.open("wb") as fh:
        plistlib.dump(data, fh, sort_keys=False)
    return _bootstrap("com.aiwindow.widget", path)
