from __future__ import annotations

import glob
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from ai_window.cli import ProviderConfig, log_path, parse_hhmm, state_dir, wake_time

APP_BUNDLE_NAME = "AI Usage Window Scheduler.app"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_app_bundle() -> Path | None:
    """Return the running .app bundle for a frozen macOS build."""
    if not is_frozen():
        return None
    try:
        executable = Path(sys.executable).resolve()
        bundle = executable.parents[2]
    except (IndexError, OSError):
        return None
    return bundle if bundle.suffix == ".app" else None


def running_from_disk_image() -> bool:
    bundle = current_app_bundle()
    return bool(bundle and str(bundle).startswith("/Volumes/"))


def cleanup_legacy_installation(current_bundle: Path | None = None) -> list[str]:
    """Remove known pre-standalone installs while preserving config/state.

    This intentionally deletes only paths created by earlier AI Window installers.
    User configuration (~/.config/ai-window) and usage/state
    (~/.local/state/ai-window) are never touched.
    """
    current_bundle = current_bundle or current_app_bundle()
    removed: list[str] = []

    # Never mutate installed copies while executing directly from a mounted DMG.
    if current_bundle and str(current_bundle).startswith("/Volumes/"):
        return removed

    home = Path.home()
    known_app_copies = [
        home / "Applications" / APP_BUNDLE_NAME,
        Path("/Applications") / APP_BUNDLE_NAME,
    ]

    current_resolved = None
    if current_bundle:
        try:
            current_resolved = current_bundle.resolve()
        except OSError:
            current_resolved = current_bundle

    for candidate in known_app_copies:
        if not candidate.exists():
            continue
        try:
            candidate_resolved = candidate.resolve()
        except OSError:
            candidate_resolved = candidate
        if current_resolved is not None and candidate_resolved == current_resolved:
            continue

        # A normal DMG install lands in /Applications. In that case, remove the
        # legacy ~/Applications copy created by the shell installer. Do not try
        # to delete another /Applications copy when running from a user-level app.
        if current_resolved and str(current_resolved).startswith("/Applications/"):
            if candidate == home / "Applications" / APP_BUNDLE_NAME:
                shutil.rmtree(candidate, ignore_errors=True)
                if not candidate.exists():
                    removed.append(str(candidate))

    # v0.1-v0.3 shell installers created a private venv/runtime here. Standalone
    # builds no longer need it.
    legacy_runtime = home / ".local" / "share" / "ai-window"
    if legacy_runtime.exists():
        shutil.rmtree(legacy_runtime, ignore_errors=True)
        if not legacy_runtime.exists():
            removed.append(str(legacy_runtime))

    # Remove only the symlink that points into the legacy runtime; never delete a
    # user-owned unrelated executable named ai-window.
    legacy_cli = home / ".local" / "bin" / "ai-window"
    if legacy_cli.is_symlink():
        try:
            target = legacy_cli.resolve(strict=False)
        except OSError:
            target = Path("")
        if str(legacy_runtime) in str(target):
            try:
                legacy_cli.unlink()
                removed.append(str(legacy_cli))
            except OSError:
                pass

    return removed


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
