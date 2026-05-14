from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from rich.console import Console

from codex_switcher.models import Session
from codex_switcher.cli.tui import CodexSwitcherTui


class CodexSwitcherTuiTest(unittest.TestCase):
    def test_global_refresh_includes_active_session(self) -> None:
        refreshed: list[str] = []
        sessions = [
            Session("inactive@example.com", "work", __file__, "inactive", active=False),
            Session("active@example.com", "work", __file__, "active", active=True),
        ]
        tui = CodexSwitcherTui.__new__(CodexSwitcherTui)
        tui.console = Console(file=io.StringIO(), force_terminal=False)
        tui.config = type("Config", (), {"refresh_delay_seconds": 0})()
        tui._refresh_one = lambda session, preserve_cache_on_error=False: refreshed.append(session.email)
        tui._pause = lambda: None

        with patch("codex_switcher.cli.tui.IntPrompt.ask", return_value=0), patch("codex_switcher.cli.tui.time.sleep"):
            tui._refresh_all_slowly(sessions)

        self.assertEqual(["inactive@example.com", "active@example.com"], refreshed)


if __name__ == "__main__":
    unittest.main()
