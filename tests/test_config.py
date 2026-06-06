from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_switcher.backend.service import SwitcherService
from codex_switcher.config import Config


class ConfigTest(unittest.TestCase):
    def test_default_switcher_home_uses_shared_offline_folder(self) -> None:
        config = Config.load()

        self.assertEqual(Path("/Users/Shared/Offline/codex-switcher"), config.switcher_home)
        self.assertNotIn("Documents", config.sessions_dir.parts)
        self.assertNotIn(Path.home() / "Documents" / "codex-switcher", config.legacy_switcher_homes)

    def test_service_migrates_existing_codex_switcher_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy_home = root / ".codex" / "codex-switcher"
            offline_home = root / "Offline" / "codex-switcher"
            source_session = legacy_home / "sessions" / "work" / "old@example.com.json"
            source_session.parent.mkdir(parents=True)
            source_session.write_text('{"token":"old"}', encoding="utf-8")

            config = Config(
                codex_home=root / ".codex",
                switcher_home=offline_home,
                sessions_dir=offline_home / "sessions",
                auth_path=root / ".codex" / "auth.json",
                cache_path=offline_home / "limits-cache.json",
                codex_binary=Path("/Applications/Codex.app/Contents/Resources/codex"),
                legacy_switcher_homes=(legacy_home,),
            )

            SwitcherService(config)

            self.assertTrue((offline_home / "sessions" / "work" / "old@example.com.json").exists())
            self.assertFalse(source_session.exists())


if __name__ == "__main__":
    unittest.main()
