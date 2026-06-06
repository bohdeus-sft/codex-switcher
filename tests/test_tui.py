from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from rich.console import Console

from codex_switcher.models import Session
from codex_switcher.cli.tui import CodexSwitcherTui


class CodexSwitcherTuiTest(unittest.TestCase):
    def test_switch_refreshes_active_session_before_switching(self) -> None:
        refreshed: list[str] = []
        switched: list[str] = []
        sessions = [
            Session("target@example.com", "work", __file__, "target", active=False),
            Session("active@example.com", "work", __file__, "active", active=True),
        ]
        tui = CodexSwitcherTui.__new__(CodexSwitcherTui)
        tui.console = Console(file=io.StringIO(), force_terminal=False)
        tui.codex_app = type("CodexApp", (), {"switch_to": lambda _self, session: switched.append(session.email)})()
        tui._pick_session = lambda _sessions: sessions[0]
        tui._refresh_one = lambda session: refreshed.append(session.email)
        tui._pause = lambda: None

        tui._switch(sessions)

        self.assertEqual(["active@example.com"], refreshed)
        self.assertEqual(["target@example.com"], switched)

    def test_prepare_login_refreshes_active_session_before_removing_auth(self) -> None:
        refreshed: list[str] = []
        sessions = [
            Session("active@example.com", "work", __file__, "active", active=True),
        ]
        tui = CodexSwitcherTui.__new__(CodexSwitcherTui)
        tui.console = Console(file=io.StringIO(), force_terminal=False)
        tui.store = type("Store", (), {"list_sessions": lambda _self: sessions})()
        tui.codex_app = type(
            "CodexApp",
            (),
            {
                "prepare_login": lambda _self: None,
                "open": lambda _self: None,
            },
        )()
        tui._refresh_one = lambda session: refreshed.append(session.email)
        tui._pause = lambda: None

        with patch("codex_switcher.cli.tui.Confirm.ask", side_effect=[True, False]):
            tui._prepare_login()

        self.assertEqual(["active@example.com"], refreshed)


if __name__ == "__main__":
    unittest.main()
