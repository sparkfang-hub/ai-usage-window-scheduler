import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from ai_window.cli import (
    AppConfig,
    ProviderConfig,
    WeeklyReset,
    launchd_weekday,
    load_config,
    next_occurrence,
    parse_days,
    save_config,
    wake_time,
)


class SchedulerTests(unittest.TestCase):
    def test_wake_time(self):
        self.assertEqual(wake_time("09:00", 120), "07:00")
        self.assertEqual(wake_time("01:00", 120), "23:00")

    def test_parse_days(self):
        self.assertEqual(parse_days("weekdays"), [0, 1, 2, 3, 4])
        self.assertEqual(parse_days("sun,mon"), [0, 6])

    def test_next_occurrence(self):
        now = datetime(2026, 8, 21, 6, 30, tzinfo=timezone.utc)
        nxt = next_occurrence("07:00", [0, 1, 2, 3, 4], now)
        self.assertEqual(nxt, datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc))

    def test_launchd_weekday(self):
        self.assertEqual(launchd_weekday(0), 1)
        self.assertEqual(launchd_weekday(6), 0)

    def test_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
            cfg = AppConfig(providers={
                "claude": ProviderConfig(
                    work_start="09:00",
                    lead_minutes=120,
                    model="haiku",
                    weekly_resets={"all_models": WeeklyReset(weekday=6, time="14:00")},
                )
            })
            save_config(cfg)
            loaded = load_config()
            self.assertEqual(loaded.providers["claude"].model, "haiku")
            self.assertEqual(loaded.providers["claude"].weekly_resets["all_models"].weekday, 6)


if __name__ == "__main__":
    unittest.main()
