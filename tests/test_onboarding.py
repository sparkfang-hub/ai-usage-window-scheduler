import os
import tempfile
import unittest
from unittest.mock import patch

from ai_window.cli import load_config
from ai_window.onboarding import configure_daily_claude, current_claude_wake_time


class OnboardingTests(unittest.TestCase):
    def test_default_wake_time_is_0500(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
            self.assertEqual(current_claude_wake_time(), "05:00")

    def test_one_field_setup_creates_daily_claude_schedule(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
            with patch("ai_window.onboarding.install_schedule", return_value=(True, "ok")):
                ok, _message = configure_daily_claude("05:00")
            self.assertTrue(ok)
            cfg = load_config().providers["claude"]
            self.assertEqual(cfg.work_start, "05:00")
            self.assertEqual(cfg.lead_minutes, 0)
            self.assertEqual(cfg.days, list(range(7)))
            self.assertEqual(cfg.window_minutes, 300)


if __name__ == "__main__":
    unittest.main()
