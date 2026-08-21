import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from ai_window.cli_v2 import cmd_ingest_claude_statusline, cmd_usage_set
from ai_window.cli import AppConfig
from ai_window.usage import build_usage_snapshot, normalize_provider, parse_percent


class Args:
    pass


class UniversalUsageTests(unittest.TestCase):
    def test_custom_provider_snapshot(self):
        state = {"usage": {"perplexity-ai": {"weekly": {"scope": "weekly", "used_percent": 58.0, "reset_at": None}}}}
        rows = build_usage_snapshot(AppConfig(), state)
        self.assertTrue(any(row["provider"] == "perplexity-ai" for row in rows))

    def test_percent_and_provider_validation(self):
        self.assertEqual(parse_percent("42.5"), 42.5)
        self.assertEqual(normalize_provider("Perplexity AI"), "perplexity-ai")
        with self.assertRaises(ValueError):
            parse_percent(101)

    def test_claude_statusline_ingest(self):
        payload = {
            "rate_limits": {
                "five_hour": {"used_percentage": 24, "resets_at": 1787292000},
                "seven_day": {"used_percentage": 41, "resets_at": 1787700000},
            }
        }
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"XDG_STATE_HOME": td, "XDG_CONFIG_HOME": td}), patch("sys.stdin", io.StringIO(json.dumps(payload))):
            out = io.StringIO()
            with redirect_stdout(out):
                rc = cmd_ingest_claude_statusline(Args())
            self.assertEqual(rc, 0)
            self.assertIn("5h 24%", out.getvalue())


if __name__ == "__main__":
    unittest.main()
