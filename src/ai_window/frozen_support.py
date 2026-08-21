from __future__ import annotations

import glob
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


def runtime_path_env() -> str:
    """Return a GUI-safe PATH that can find common AI CLI installations.

    Finder-launched macOS apps do not inherit the interactive shell PATH, so a
    CLI that works in Terminal can otherwise appear to be missing. Keep this
    resolver local-only and credential-free.
    """
    home = str(Path.home())
    parts = [
        f"{home}/.local/bin",
        f"{home}/.claude/bin",
        f"{home}/.npm-global/bin",
        f"{home}/.bun/bin",
        f"{home}/.volta/bin",
        f"{home}/Library/pnpm",
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]

    # nvm installs Node-based CLIs under a versioned directory that Finder does
    # not know about. Prefer newer paths first but include all discovered bins.
    nvm_bins = sorted(
        glob.glob(f"{home}/.nvm/versions/node/*/bin"),
        reverse=True,
    )
    parts.extend(nvm_bins)

    inherited = os.environ.get("PATH", "")
    if inherited:
        parts.extend(inherited.split(":"))

    # Preserve order while removing duplicates/empty entries.
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.add(part)
            unique.append(part)
    return ":".join(unique)


def activate_runtime_path() -> str:
    path = runtime_path_env()
    os.environ["PATH"] = path
    return path


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
        "EnvironmentVariables": {"HOME": str(Path.home()), "PATH": runtime_path_env()},
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
        "EnvironmentVariables": {"HOME": str(Path.home()), "PATH": runtime_path_env()},
    }
    with path.open("wb") as fh:
        plistlib.dump(data, fh, sort_keys=False)
    return _bootstrap("com.aiwindow.widget", path)
