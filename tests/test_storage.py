from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_switcher.config import Config
from codex_switcher.models import LimitWindow
from codex_switcher.storage import SessionStore, sanitize_part, snapshot_from_json


class SessionStoreTest(unittest.TestCase):
    def test_lists_flat_and_categorized_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _config(root)
            (config.sessions_dir / "work").mkdir(parents=True)
            (config.sessions_dir / "personal@example.com.json").write_text("a", encoding="utf-8")
            (config.sessions_dir / "work" / "dev@example.com.json").write_text("b", encoding="utf-8")
            config.auth_path.parent.mkdir(parents=True, exist_ok=True)
            config.auth_path.write_text("b", encoding="utf-8")

            sessions = SessionStore(config).list_sessions()

            self.assertEqual(["personal@example.com", "dev@example.com"], [item.email for item in sessions])
            self.assertEqual(["default", "work"], [item.display_category for item in sessions])
            self.assertEqual([False, True], [item.active for item in sessions])

    def test_destination_sanitizes_email_and_category(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = _config(Path(temp_dir))
            store = SessionStore(config)

            destination = store.destination_for(" name+test@example.com ", "work clients")

            self.assertEqual(config.sessions_dir / "work_clients" / "name+test@example.com.json", destination)

    def test_sanitize_part_removes_unsafe_path_chars(self) -> None:
        self.assertEqual("a_b_c", sanitize_part("../a/b c"))

    def test_loads_cached_limit_window_snake_case(self) -> None:
        snapshot = snapshot_from_json(
            {
                "fetched_at": 1778613100,
                "primary": {
                    "resets_at": 1778628172,
                    "used_percent": 46.0,
                    "window_duration_mins": 300,
                },
                "secondary": None,
                "plan_type": "plus",
                "reached_type": None,
                "error": None,
            }
        )

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(LimitWindow(46.0, 300, 1778628172), snapshot.primary)


def _config(root: Path) -> Config:
    codex_home = root / ".codex"
    return Config(
        codex_home=codex_home,
        switcher_home=codex_home / "codex-switcher",
        sessions_dir=codex_home / "codex-switcher" / "sessions",
        auth_path=codex_home / "auth.json",
        cache_path=codex_home / "codex-switcher" / "limits-cache.json",
        codex_binary=root / "codex",
    )


if __name__ == "__main__":
    unittest.main()
