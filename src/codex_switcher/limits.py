from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from select import select
from typing import Any

from .config import Config
from .models import LimitSnapshot, LimitWindow, Session
from .storage import now_ts


class LimitReader:
    def __init__(self, config: Config) -> None:
        self.config = config

    def read(self, session: Session, timeout_seconds: float = 30.0) -> LimitSnapshot:
        if not self.config.codex_binary.exists():
            return LimitSnapshot.error_snapshot(now_ts(), f"codex binary not found: {self.config.codex_binary}")

        try:
            with tempfile.TemporaryDirectory(prefix="codex-switcher-limits-") as temp_dir:
                codex_home = Path(temp_dir)
                shutil.copyfile(session.path, codex_home / "auth.json")
                (codex_home / "auth.json").chmod(0o600)
                return self._read_from_app_server(codex_home, timeout_seconds)
        except Exception as exc:
            return LimitSnapshot.error_snapshot(now_ts(), str(exc))

    def _read_from_app_server(self, codex_home: Path, timeout_seconds: float) -> LimitSnapshot:
        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home)
        env.setdefault("RUST_LOG", "off")

        process = subprocess.Popen(
            [
                str(self.config.codex_binary),
                "-s",
                "read-only",
                "-a",
                "untrusted",
                "app-server",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )

        try:
            self._send(process, {"method": "initialize", "id": 1, "params": _initialize_params()})
            initialize = self._read_response(process, 1, timeout_seconds)
            if "error" in initialize:
                raise RuntimeError(_rpc_error_message(initialize["error"]))

            self._send(process, {"method": "initialized", "params": {}})
            self._send(process, {"method": "account/read", "id": 2, "params": {"refreshToken": True}})
            account = self._read_response(process, 2, timeout_seconds)
            if "error" in account:
                raise RuntimeError(_rpc_error_message(account["error"]))

            self._send(process, {"method": "account/rateLimits/read", "id": 3})
            limits = self._read_response(process, 3, timeout_seconds)
            if "error" in limits:
                raise RuntimeError(_rpc_error_message(limits["error"]))

            return _parse_rate_limits(limits.get("result", {}), account.get("result", {}))
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()

    @staticmethod
    def _send(process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
        if process.stdin is None:
            raise RuntimeError("app-server stdin is closed")
        process.stdin.write(json.dumps(payload) + "\n")
        process.stdin.flush()

    @staticmethod
    def _read_response(process: subprocess.Popen[str], response_id: int, timeout_seconds: float) -> dict[str, Any]:
        if process.stdout is None:
            raise RuntimeError("app-server stdout is closed")

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"app-server exited with code {process.returncode}")
            ready, _, _ = select([process.stdout], [], [], 0.25)
            if not ready:
                continue
            line = process.stdout.readline()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == response_id:
                return message

        raise TimeoutError(f"timeout waiting for app-server response id {response_id}")


def _initialize_params() -> dict[str, Any]:
    return {
        "clientInfo": {
            "name": "codex_switcher",
            "title": "Codex Switcher",
            "version": "0.1.0",
        },
        "capabilities": {
            "optOutNotificationMethods": [
                "account/updated",
                "account/rateLimits/updated",
                "thread/started",
                "thread/status/changed",
            ]
        },
    }


def _parse_rate_limits(result: dict[str, Any], account_result: dict[str, Any]) -> LimitSnapshot:
    rate_limits = result.get("rateLimits") if isinstance(result, dict) else {}
    if not isinstance(rate_limits, dict):
        rate_limits = {}

    account = account_result.get("account") if isinstance(account_result, dict) else {}
    if not isinstance(account, dict):
        account = {}

    return LimitSnapshot(
        fetched_at=now_ts(),
        primary=LimitWindow.from_payload(rate_limits.get("primary")),
        secondary=LimitWindow.from_payload(rate_limits.get("secondary")),
        plan_type=_first_str(rate_limits.get("planType"), account.get("planType")),
        reached_type=_first_str(rate_limits.get("rateLimitReachedType")),
        error=None,
    )


def _first_str(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _rpc_error_message(error: Any) -> str:
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
    return str(error)
