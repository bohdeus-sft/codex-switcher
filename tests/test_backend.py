from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from subprocess import run

from fastapi.testclient import TestClient

from codex_switcher.backend.server import create_app


class BackendApiTest(unittest.TestCase):
    def test_state_matches_frontend_shape(self) -> None:
        service = FakeService()
        client = TestClient(create_app(service=service))

        response = client.get("/api/state")

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "sessions": [
                    {
                        "id": "work/dev@example.com",
                        "key": "work/dev@example.com",
                        "account": "dev@example.com",
                        "email": "dev@example.com",
                        "category": "work",
                        "displayCategory": "work",
                        "fingerprint": "abc123",
                        "active": True,
                        "capturedAt": "May 13 01:00",
                        "fiveHour": {"remaining": 75, "reset": "02:00"},
                        "weekly": None,
                    }
                ],
                "activeAuthExists": True,
                "paths": {
                    "auth": "/tmp/auth.json",
                    "sessions": "/tmp/sessions",
                    "cache": "/tmp/cache.json",
                },
            },
            response.json(),
        )

    def test_frontend_actions_call_matching_service_methods(self) -> None:
        service = FakeService()
        client = TestClient(create_app(service=service))

        self.assertEqual(200, client.post("/api/auth/prepare-login").status_code)
        self.assertEqual(200, client.post("/api/auth/prepare-login", json={"openCodex": True}).status_code)
        self.assertEqual(200, client.post("/api/auth/remove-active").status_code)
        self.assertEqual(200, client.post("/api/sessions/capture", json={"email": "new@example.com", "category": "qa"}).status_code)
        self.assertEqual(200, client.post("/api/sessions/switch", json={"key": "work/dev@example.com"}).status_code)
        self.assertEqual(200, client.post("/api/sessions/refresh", json={"key": "work/dev@example.com"}).status_code)
        self.assertEqual(200, client.post("/api/sessions/refresh-all").status_code)
        self.assertEqual(200, client.delete("/api/sessions/work%2Fdev@example.com").status_code)

        self.assertEqual(
            [
                ("prepare_login", False),
                ("prepare_login", True),
                ("remove_active_auth",),
                ("capture_current", "new@example.com", "qa"),
                ("switch_to", "work/dev@example.com"),
                ("refresh_one", "work/dev@example.com"),
                ("refresh_all",),
                ("delete_session", "work/dev@example.com"),
            ],
            service.calls,
        )

    def test_errors_use_frontend_error_shape(self) -> None:
        service = FakeService()
        client = TestClient(create_app(service=service))

        response = client.post("/api/sessions/capture", json={"email": "   ", "category": "qa"})

        self.assertEqual(400, response.status_code)
        self.assertEqual({"ok": False, "error": "email is required"}, response.json())

    def test_serves_built_frontend_and_spa_fallback(self) -> None:
        service = FakeService()
        with tempfile.TemporaryDirectory() as temp_dir:
            static_root = Path(temp_dir)
            (static_root / "index.html").write_text("<main>Codex Switcher</main>", encoding="utf-8")
            client = TestClient(create_app(service=service, static_root=static_root))

            self.assertIn("Codex Switcher", client.get("/").text)
            self.assertIn("Codex Switcher", client.get("/sessions").text)
            self.assertEqual(200, client.head("/").status_code)

    def test_server_file_can_run_directly_for_pycharm(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        server_path = repo_root / "src" / "codex_switcher" / "backend" / "server.py"

        result = run(
            [str(repo_root / ".venv" / "bin" / "python"), str(server_path), "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.stderr, "")
        self.assertEqual(0, result.returncode)
        self.assertIn("Run the local Codex Switcher backend.", result.stdout)


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def state(self) -> dict[str, object]:
        return {
            "sessions": [
                {
                    "id": "work/dev@example.com",
                    "key": "work/dev@example.com",
                    "account": "dev@example.com",
                    "email": "dev@example.com",
                    "category": "work",
                    "displayCategory": "work",
                    "fingerprint": "abc123",
                    "active": True,
                    "capturedAt": "May 13 01:00",
                    "fiveHour": {"remaining": 75, "reset": "02:00"},
                    "weekly": None,
                }
            ],
            "activeAuthExists": True,
            "paths": {
                "auth": "/tmp/auth.json",
                "sessions": "/tmp/sessions",
                "cache": "/tmp/cache.json",
            },
        }

    def prepare_login(self, open_codex: bool = False) -> dict[str, object]:
        self.calls.append(("prepare_login", open_codex))
        return {"ok": True, "message": "prepared"}

    def remove_active_auth(self) -> dict[str, object]:
        self.calls.append(("remove_active_auth",))
        return {"ok": True, "message": "removed"}

    def capture_current(self, email: str, category: str = "") -> dict[str, object]:
        self.calls.append(("capture_current", email, category))
        return {"ok": True, "message": "captured"}

    def switch_to(self, key: str) -> dict[str, object]:
        self.calls.append(("switch_to", key))
        return {"ok": True, "message": "switched"}

    def refresh_one(self, key: str) -> dict[str, object]:
        self.calls.append(("refresh_one", key))
        return {"ok": True, "message": "refreshed"}

    def refresh_all(self) -> dict[str, object]:
        self.calls.append(("refresh_all",))
        return {"ok": True, "message": "refreshed all"}

    def delete_session(self, key: str) -> dict[str, object]:
        self.calls.append(("delete_session", key))
        return {"ok": True, "message": "deleted"}


if __name__ == "__main__":
    unittest.main()
