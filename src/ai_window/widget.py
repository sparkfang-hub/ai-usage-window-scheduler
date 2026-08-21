from __future__ import annotations

from datetime import datetime
from typing import Any

from ai_window.usage import build_usage_snapshot, format_countdown


def _summary_title(row: dict[str, Any], now: datetime) -> str:
    used = row.get("max_used_percent")
    reset = row.get("next_reset")
    parts = [row["display_name"]]
    if used is not None:
        parts.append(f"{used:.0f}% used")
    else:
        parts.append("usage n/a")
    if reset is not None:
        parts.append(f"reset {format_countdown(reset, now)}")
    return " · ".join(parts)


def run_widget() -> int:
    try:
        import rumps  # type: ignore
    except ImportError:
        print("Menu-bar widget dependency is missing. Reinstall with: pip install 'ai-usage-window-scheduler[widget]'", flush=True)
        return 1

    # Delayed import avoids a circular import while cli.py lazily imports this module.
    from ai_window.cli import load_config, load_state

    class AIWindowMenuBar(rumps.App):
        def __init__(self) -> None:
            super().__init__("AI", title="AI", quit_button=None)
            self._timer = rumps.Timer(self.refresh, 60)
            self.refresh(None)
            self._timer.start()

        def refresh(self, _sender: Any) -> None:
            now = datetime.now().astimezone()
            snapshot = build_usage_snapshot(load_config(), load_state(), now)
            self.menu.clear()

            used_values = [row["max_used_percent"] for row in snapshot if row.get("max_used_percent") is not None]
            self.title = f"AI {max(used_values):.0f}%" if used_values else "AI"

            for row in snapshot:
                parent = rumps.MenuItem(_summary_title(row, now))
                if row["records"]:
                    for record in row["records"]:
                        used = record.get("used_percent")
                        usage_text = f"{float(used):.1f}% used" if used is not None else "usage n/a"
                        reset_dt = record.get("reset_dt")
                        reset_text = (
                            f"reset {format_countdown(reset_dt, now)} · {reset_dt.strftime('%a %H:%M')}"
                            if reset_dt
                            else "reset unknown"
                        )
                        source = record.get("source") or "unknown"
                        parent.add(rumps.MenuItem(f"{record.get('scope', 'primary')}: {usage_text} · {reset_text} · {source}"))
                else:
                    parent.add(rumps.MenuItem("No usage data yet"))
                self.menu.add(parent)

            self.menu.add(None)
            self.menu.add(rumps.MenuItem("Refresh", callback=self.refresh))
            self.menu.add(rumps.MenuItem("Quit AI Window", callback=lambda _sender: rumps.quit_application()))

    AIWindowMenuBar().run()
    return 0
