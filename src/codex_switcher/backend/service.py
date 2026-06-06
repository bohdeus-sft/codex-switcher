from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from codex_switcher.codex_app import CodexApp
from codex_switcher.config import Config
from codex_switcher.limits import LimitReader
from codex_switcher.models import LimitSnapshot, LimitWindow, Session
from codex_switcher.storage import SessionStore


class SwitcherService:
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.load()
        self._migrate_legacy_switcher_home()
        self.store = SessionStore(self.config)
        self.codex_app = CodexApp(self.config)
        self.limit_reader = LimitReader(self.config)
        self.snapshots = self.store.load_cache()

    def _migrate_legacy_switcher_home(self) -> None:
        for legacy in self.config.legacy_switcher_homes:
            self._migrate_switcher_home(legacy)

    def _migrate_switcher_home(self, legacy: Path) -> None:
        target = self.config.switcher_home
        if legacy == target or not legacy.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            for source in legacy.rglob("*"):
                if source.is_dir():
                    continue
                relative = source.relative_to(legacy)
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    shutil.move(str(source), str(destination))
            shutil.rmtree(legacy, ignore_errors=True)
        else:
            shutil.move(str(legacy), str(target))

    def state(self) -> dict[str, Any]:
        self.store.ensure()
        sessions = self.store.list_sessions()
        self.snapshots = self.store.load_cache()
        return {
            "sessions": [self._session_to_json(session) for session in sessions],
            "activeAuthExists": self.config.auth_path.exists(),
            "paths": {
                "auth": str(self.config.auth_path),
                "sessions": str(self.config.sessions_dir),
                "cache": str(self.config.cache_path),
            },
        }

    def prepare_login(self, open_codex: bool = False) -> dict[str, Any]:
        previous = self._refresh_active_before_leaving()
        self.codex_app.prepare_login()
        if open_codex:
            time.sleep(2)
            self.codex_app.open()
        return {
            **self._ok(
                f"{self._leaving_message(previous, 'preparing clean login')} Active auth.json removed locally."
            ),
            **self._leaving_payload(previous),
        }

    def open_codex(self) -> dict[str, Any]:
        self.codex_app.open()
        return self._ok("Codex.app open command sent.")

    def open_path(self, key: str) -> dict[str, Any]:
        targets = {
            "auth": self.config.auth_path,
            "sessions": self.config.sessions_dir,
            "cache": self.config.cache_path,
        }
        if key not in targets:
            raise ValueError(f"unknown path key: {key}")
        path = targets[key]
        if key == "sessions":
            path.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            raise FileNotFoundError(f"path does not exist: {path}")
        if sys.platform != "darwin":
            return self._ok(f"Open is macOS-only; path is {path}.")
        reveal = path.is_file()
        cmd = ["open", "-R", str(path)] if reveal else ["open", str(path)]
        subprocess.run(cmd, check=False)
        return self._ok(f"Opened {path} in Finder.")

    def remove_active_auth(self) -> dict[str, Any]:
        previous = self._refresh_active_before_leaving()
        self.codex_app.stop()
        self.codex_app.remove_active_auth()
        return {
            **self._ok(
                f"{self._leaving_message(previous, 'removing active auth')} Active auth.json removed locally."
            ),
            **self._leaving_payload(previous),
        }

    def capture_current(self, email: str, category: str = "") -> dict[str, Any]:
        destination = self.store.destination_for(email, category)
        self.codex_app.save_current_auth(destination)
        return {
            **self._ok(f"Saved current auth.json as {destination.relative_to(self.config.sessions_dir)}."),
            "session": self._session_to_json(self._session_by_path(destination)),
        }

    def switch_to(self, key: str) -> dict[str, Any]:
        session = self._session_by_key(key)
        previous = self._refresh_active_before_leaving(exclude_key=session.key)
        self.codex_app.switch_to(session)
        if previous is None:
            message = f"Switched to {session.email}. No different saved active account was found to refresh."
        else:
            previous_session, snapshot = previous
            message = (
                f"Switched from {previous_session.email} to {session.email}. "
                f"{self._limit_update_message(previous_session, snapshot, 'switching')}"
            )
        return {
            **self._ok(message),
            "session": self._session_to_json(session),
            **self._leaving_payload(previous),
        }

    def delete_session(self, key: str) -> dict[str, Any]:
        session = self._session_by_key(key)
        session_path = session.path.resolve()
        sessions_root = self.config.sessions_dir.resolve()
        if sessions_root not in session_path.parents:
            raise ValueError("session path is outside sessions directory")
        session.path.unlink()
        return self._ok(f"Deleted saved session {session.email}.")

    def _refresh_active_before_leaving(
        self,
        exclude_key: str | None = None,
    ) -> tuple[Session, LimitSnapshot] | None:
        active = self._active_session(exclude_key)
        if active is None:
            return None
        snapshot = self.limit_reader.read(active)
        self.snapshots[self.store.cache_key(active)] = snapshot
        self.store.save_cache(self.snapshots)
        return active, snapshot

    def _active_session(self, exclude_key: str | None = None) -> Session | None:
        for session in self.store.list_sessions():
            if session.active and session.key != exclude_key:
                return session
        return None

    def _leaving_message(
        self,
        previous: tuple[Session, LimitSnapshot] | None,
        action: str,
    ) -> str:
        if previous is None:
            return f"No saved active account was found to refresh before {action}."
        session, snapshot = previous
        return self._limit_update_message(session, snapshot, action)

    def _limit_update_message(self, session: Session, snapshot: LimitSnapshot, action: str) -> str:
        if snapshot.error:
            return f"Limit refresh for {session.email} failed before {action}: {snapshot.error}"
        return f"Updated limits for {session.email} before {action}."

    def _leaving_payload(self, previous: tuple[Session, LimitSnapshot] | None) -> dict[str, Any]:
        if previous is None:
            return {}
        session, snapshot = previous
        return {"switchedFrom": self._session_to_json(session, snapshot)}

    def _session_by_key(self, key: str) -> Session:
        for session in self.store.list_sessions():
            if session.key == key:
                return session
        raise KeyError(f"session not found: {key}")

    def _session_by_path(self, path: Path) -> Session:
        resolved = path.resolve()
        for session in self.store.list_sessions():
            if session.path.resolve() == resolved:
                return session
        raise KeyError(f"session not found: {path}")

    def _session_to_json(
        self,
        session: Session,
        snapshot: LimitSnapshot | None = None,
    ) -> dict[str, Any]:
        current_snapshot = snapshot if snapshot is not None else self.snapshots.get(self.store.cache_key(session))
        return {
            "key": session.key,
            "id": session.key,
            "email": session.email,
            "account": session.email,
            "category": session.category,
            "displayCategory": session.display_category,
            "path": str(session.path),
            "fingerprint": session.fingerprint,
            "active": session.active,
            "capturedAt": datetime.fromtimestamp(session.path.stat().st_mtime).strftime("%b %d %H:%M"),
            "limits": snapshot_to_api(current_snapshot),
            "fiveHour": limit_window_to_api(pick_window(current_snapshot, 300), current_snapshot),
            "weekly": limit_window_to_api(pick_window(current_snapshot, 10080), current_snapshot),
        }

    @staticmethod
    def _ok(message: str) -> dict[str, str | bool]:
        return {"ok": True, "message": message}


def pick_window(snapshot: LimitSnapshot | None, duration_mins: int) -> LimitWindow | None:
    if snapshot is None:
        return None
    for window in (snapshot.primary, snapshot.secondary):
        if window and window.window_duration_mins == duration_mins:
            return window
    if duration_mins == 300:
        return snapshot.primary
    if duration_mins == 10080:
        return snapshot.secondary
    return None


def limit_window_to_api(
    window: LimitWindow | None,
    snapshot: LimitSnapshot | None,
) -> dict[str, Any] | None:
    if snapshot and snapshot.error:
        return {"remaining": None, "reset": "error", "error": snapshot.error}
    if window is None:
        return None
    return {
        "remaining": None if window.used_percent is None else max(0, round(100 - window.used_percent)),
        "reset": reset_label(window.resets_at),
        "usedPercent": window.used_percent,
        "windowDurationMins": window.window_duration_mins,
        "resetsAt": window.resets_at,
    }


def snapshot_to_api(snapshot: LimitSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        **asdict(snapshot),
        "primary": limit_window_to_api(snapshot.primary, snapshot),
        "secondary": limit_window_to_api(snapshot.secondary, snapshot),
    }


def reset_label(resets_at: int | None) -> str:
    if not resets_at:
        return "unknown"

    from datetime import datetime

    return datetime.fromtimestamp(resets_at).strftime("%b %d %H:%M")
