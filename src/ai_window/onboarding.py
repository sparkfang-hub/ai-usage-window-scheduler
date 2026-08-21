from __future__ import annotations

import subprocess
import sys
from dataclasses import replace

from ai_window.cli import (
    ProviderConfig,
    install_schedule,
    load_config,
    parse_hhmm,
    provider_doctor,
    save_config,
    wake_time,
)


def _osascript(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["osascript", "-e", script, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _alert(message: str, title: str = "AI Usage Window Scheduler") -> None:
    script = '''
on run argv
    display alert (item 1 of argv) message (item 2 of argv) as informational buttons {"OK"} default button "OK"
end run
'''
    _osascript(script, title, message)


def _notify(message: str) -> None:
    script = '''
on run argv
    display notification (item 1 of argv) with title "AI Usage Window Scheduler"
end run
'''
    _osascript(script, message)


def current_claude_wake_time() -> str:
    config = load_config()
    cfg = config.providers.get("claude")
    if not cfg:
        return "05:00"
    return wake_time(cfg.work_start, cfg.lead_minutes)


def prompt_wake_time(default_time: str | None = None) -> str | None:
    default_time = default_time or current_claude_wake_time()
    script = '''
on run argv
    set defaultTime to item 1 of argv
    try
        set resultDialog to display dialog "每天要幾點自動啟動 Claude？\n\n只要輸入時間就好，例如 05:00。每天都會執行，包含週末。" default answer defaultTime buttons {"取消", "儲存"} default button "儲存" cancel button "取消" with title "AI Usage Window Scheduler"
        return text returned of resultDialog
    on error number -128
        return "__CANCEL__"
    end try
end run
'''

    while True:
        proc = _osascript(script, default_time)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Could not open macOS setup dialog").strip())
        value = proc.stdout.strip()
        if value == "__CANCEL__":
            return None
        try:
            parse_hhmm(value)
            return value
        except ValueError:
            _alert("時間格式不對。請使用 24 小時制 HH:MM，例如 05:00。")
            default_time = value or default_time


def configure_daily_claude(wake_at: str) -> tuple[bool, str]:
    parse_hhmm(wake_at)
    config = load_config()
    old = config.providers.get("claude", ProviderConfig())
    cfg = replace(
        old,
        enabled=True,
        work_start=wake_at,
        lead_minutes=0,
        days=list(range(7)),
        window_minutes=300,
        model=old.model or "haiku",
    )
    config.providers["claude"] = cfg
    save_config(config)

    if bool(getattr(sys, "frozen", False)):
        from ai_window.frozen_support import install_claude_schedule

        return install_claude_schedule(cfg)
    return install_schedule("claude", cfg)


def run_onboarding(*, notify: bool = True) -> int:
    if sys.platform != "darwin":
        print("The simple setup window currently supports macOS only.", file=sys.stderr)
        return 1

    wake_at = prompt_wake_time()
    if wake_at is None:
        return 0

    ok, message = configure_daily_claude(wake_at)
    if not ok:
        _alert(f"時間已儲存，但自動排程安裝失敗：\n\n{message}")
        return 1

    doctor_ok, doctor_message = provider_doctor("claude")
    if not doctor_ok:
        _alert(
            f"每天 {wake_at} 的排程已設定完成。\n\n但目前找不到可用的 Claude Code CLI：\n{doctor_message}"
        )
        return 0

    if notify:
        _notify(f"已設定：每天 {wake_at} 自動啟動 Claude")
    return 0


def main() -> int:
    return run_onboarding()


if __name__ == "__main__":
    raise SystemExit(main())
