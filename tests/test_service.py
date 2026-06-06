from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from codex_switcher.backend.service import SwitcherService
from codex_switcher.config import Config
from codex_switcher.models import LimitSnapshot, LimitWindow, Session


class SwitcherServiceTest(unittest.TestCase):
    def test_switch_refreshes_active_session_before_switching(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service, active, target, limit_reader, codex_app = make_service(Path(temp_dir))

            result = service.switch_to(target.key)

            self.assertEqual([active.email], [session.email for session in limit_reader.reads])
            self.assertEqual([target.email], [session.email for session in codex_app.switches])
            self.assertIn(f"Switched from {active.email} to {target.email}.", result["message"])
            self.assertIn(f"Updated limits for {active.email}", result["message"])
            self.assertEqual(active.email, result["switchedFrom"]["email"])
            self.assertIsNotNone(service.store.load_cache().get(active.fingerprint))

    def test_prepare_login_refreshes_active_session_before_removing_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service, active, _target, limit_reader, codex_app = make_service(Path(temp_dir))

            result = service.prepare_login()

            self.assertEqual([active.email], [session.email for session in limit_reader.reads])
            self.assertEqual(1, codex_app.prepare_calls)
            self.assertIn(f"Updated limits for {active.email}", result["message"])
            self.assertEqual(active.email, result["switchedFrom"]["email"])


class FakeCodexApp:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.switches: list[Session] = []
        self.prepare_calls = 0
        self.remove_calls = 0

    def prepare_login(self) -> None:
        self.prepare_calls += 1
        self.remove_active_auth()

    def open(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def remove_active_auth(self) -> None:
        self.remove_calls += 1
        self.config.auth_path.unlink(missing_ok=True)

    def switch_to(self, session: Session) -> None:
        self.switches.append(session)
        self.config.auth_path.write_bytes(session.path.read_bytes())


class FakeLimitReader:
    def __init__(self) -> None:
        self.reads: list[Session] = []

    def read(self, session: Session) -> LimitSnapshot:
        self.reads.append(session)
        return LimitSnapshot(
            fetched_at=123,
            primary=LimitWindow(used_percent=25, window_duration_mins=300, resets_at=456),
            secondary=None,
            plan_type="plus",
            reached_type=None,
            error=None,
        )


def make_service(root: Path) -> tuple[SwitcherService, Session, Session, FakeLimitReader, FakeCodexApp]:
    codex_home = root / "codex"
    switcher_home = root / "switcher"
    config = Config(
        codex_home=codex_home,
        switcher_home=switcher_home,
        sessions_dir=switcher_home / "sessions",
        auth_path=codex_home / "auth.json",
        cache_path=switcher_home / "limits-cache.json",
        codex_binary=root / "codex-bin",
    )
    config.ensure_dirs()
    codex_home.mkdir(parents=True, exist_ok=True)

    active_path = config.sessions_dir / "work" / "active@example.com.json"
    target_path = config.sessions_dir / "work" / "target@example.com.json"
    active_path.parent.mkdir(parents=True, exist_ok=True)
    active_path.write_text('{"refresh_token":"active"}', encoding="utf-8")
    target_path.write_text('{"refresh_token":"target"}', encoding="utf-8")
    config.auth_path.write_text('{"refresh_token":"active"}', encoding="utf-8")

    service = SwitcherService(config)
    limit_reader = FakeLimitReader()
    codex_app = FakeCodexApp(config)
    service.limit_reader = limit_reader
    service.codex_app = codex_app

    sessions = {session.email: session for session in service.store.list_sessions()}
    return service, sessions["active@example.com"], sessions["target@example.com"], limit_reader, codex_app


if __name__ == "__main__":
    unittest.main()
