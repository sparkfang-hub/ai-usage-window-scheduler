import os
import tempfile
import unittest
from unittest.mock import patch

from ai_window.cli import load_config
from ai_window.frozen_support import runtime_path_env
from ai_window.onboarding import configure_daily_claude, current_claude_wake_time


class OnboardingTests(unittest.TestCase):
    def test_default_wake_time_is_0500(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
            self.assertEqual(current_claude_wake_time(), "05:00")

    def test_one_field_setup_creates_daily_claude_schedule(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
            with patch("ai_window.onboarding.is_frozen", return_value=False), patch(
                "ai_window.onboarding.install_schedule", return_value=(True, "ok")
            ):
                ok, _message = configure_daily_claude("05:00")
            self.assertTrue(ok)
            cfg = load_config().providers["claude"]
            self.assertEqual(cfg.work_start, "05:00")
            self.assertEqual(cfg.lead_minutes, 0)
            self.assertEqual(cfg.days, list(range(7)))
            self.assertEqual(cfg.window_minutes, 300)

    def test_frozen_app_uses_bundled_schedule_installer(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
            with patch("ai_window.onboarding.is_frozen", return_value=True), patch(
                "ai_window.onboarding.install_claude_schedule", return_value=(True, "ok")
            ) as frozen_install, patch("ai_window.onboarding.install_schedule") as legacy_install:
                ok, _message = configure_daily_claude("05:00")
            self.assertTrue(ok)
            frozen_install.assert_called_once()
            legacy_install.assert_not_called()

    def test_gui_runtime_path_includes_common_claude_location(self):
        with tempfile.TemporaryDirectory() as home, patch("pathlib.Path.home", return_value=__import__("pathlib").Path(home)):
            value = runtime_path_env()
            self.assertIn(f"{home}/.local/bin", value.split(":"))
            self.assertIn("/opt/homebrew/bin", value.split(":"))


if __name__ == "__main__":
    unittest.main()
