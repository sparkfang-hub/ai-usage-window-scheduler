from __future__ import annotations

import sys

from ai_window.cli_v2 import main as cli_main
from ai_window.onboarding import main as onboarding_main


def main() -> int:
    # Finder launch: show the one-field setup dialog.
    # LaunchAgent/helper launch: reuse this same bundled executable for CLI roles.
    args = list(sys.argv[1:])
    if args:
        return cli_main(args)

    result = onboarding_main()
    if result == 0 and bool(getattr(sys, "frozen", False)):
        from ai_window.frozen_support import install_widget_agent

        install_widget_agent()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
