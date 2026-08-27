import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_window.frozen_support import cleanup_legacy_installation


class CleanupTests(unittest.TestCase):
    def test_upgrade_removes_legacy_user_app_runtime_and_cli_but_preserves_state(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            legacy_app = home / "Applications" / "AI Usage Window Scheduler.app"
            legacy_app.mkdir(parents=True)
            legacy_runtime = home / ".local" / "share" / "ai-window"
            legacy_runtime.mkdir(parents=True)
            legacy_bin_dir = home / ".local" / "bin"
            legacy_bin_dir.mkdir(parents=True)
            legacy_cli = legacy_bin_dir / "ai-window"
            legacy_cli.symlink_to(legacy_runtime / "venv" / "bin" / "ai-window")

            config = home / ".config" / "ai-window" / "config.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"wake":"05:00"}')
            state = home / ".local" / "state" / "ai-window" / "state.json"
            state.parent.mkdir(parents=True)
            state.write_text('{"usage":{}}')

            with patch("ai_window.frozen_support.Path.home", return_value=home):
                removed = cleanup_legacy_installation(
                    current_bundle=Path("/Applications/AI Usage Window Scheduler.app")
                )

            self.assertFalse(legacy_app.exists())
            self.assertFalse(legacy_runtime.exists())
            self.assertFalse(legacy_cli.exists())
            self.assertTrue(config.exists())
            self.assertTrue(state.exists())
            self.assertTrue(any("AI Usage Window Scheduler.app" in item for item in removed))

    def test_running_from_dmg_does_not_delete_existing_install(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            legacy_app = home / "Applications" / "AI Usage Window Scheduler.app"
            legacy_app.mkdir(parents=True)
            legacy_runtime = home / ".local" / "share" / "ai-window"
            legacy_runtime.mkdir(parents=True)

            with patch("ai_window.frozen_support.Path.home", return_value=home):
                removed = cleanup_legacy_installation(
                    current_bundle=Path("/Volumes/AI Usage Window Scheduler/AI Usage Window Scheduler.app")
                )

            self.assertEqual(removed, [])
            self.assertTrue(legacy_app.exists())
            self.assertTrue(legacy_runtime.exists())


if __name__ == "__main__":
    unittest.main()
