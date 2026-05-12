from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import Config
from .models import LimitSnapshot, LimitWindow, Session

_SAFE_PART_RE = re.compile(r"[^A-Za-z0-9_.@+-]+")


class SessionStore:
    def __init__(self, config: Config) -> None:
        self.config = config

    def ensure(self) -> None:
        self.config.ensure_dirs()

    def list_sessions(self) -> list[Session]:
        self.ensure()
        active_fingerprint = self._fingerprint(self.config.auth_path)
        sessions: list[Session] = []

        for path in sorted(self.config.sessions_dir.rglob("*.json")):
            if not path.is_file():
                continue
            relative = path.relative_to(self.config.sessions_dir)
            category = "" if len(relative.parts) == 1 else "/".join(relative.parts[:-1])
            fingerprint = self._fingerprint(path)
            sessions.append(
                Session(
                    email=path.stem,
                    category=category,
                    path=path,
                    fingerprint=fingerprint,
                    active=bool(active_fingerprint and fingerprint == active_fingerprint),
                )
            )

        return sorted(sessions, key=lambda item: (item.display_category.lower(), item.email.lower()))

    def destination_for(self, email: str, category: str = "") -> Path:
        clean_email = sanitize_part(email).removesuffix(".json")
        if not clean_email:
            raise ValueError("email is empty after sanitizing")

        clean_category_parts = [sanitize_part(part) for part in category.split("/") if part.strip()]
        if any(not part for part in clean_category_parts):
            raise ValueError("category contains only unsafe characters")

        return self.config.sessions_dir.joinpath(*clean_category_parts, f"{clean_email}.json")

    def save_cache(self, snapshots: dict[str, LimitSnapshot]) -> None:
        self.config.switcher_home.mkdir(parents=True, exist_ok=True)
        payload = {key: snapshot_to_json(value) for key, value in snapshots.items()}
        self.config.cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        self.config.cache_path.chmod(0o600)

    def load_cache(self) -> dict[str, LimitSnapshot]:
        if not self.config.cache_path.exists():
            return {}
        try:
            payload = json.loads(self.config.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        snapshots: dict[str, LimitSnapshot] = {}
        for key, value in payload.items():
            snapshot = snapshot_from_json(value)
            if snapshot is not None:
                snapshots[key] = snapshot
        return snapshots

    def cache_key(self, session: Session) -> str:
        return session.fingerprint

    @staticmethod
    def _fingerprint(path: Path) -> str:
        if not path.exists() or not path.is_file():
            return ""
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


def sanitize_part(value: str) -> str:
    clean = _SAFE_PART_RE.sub("_", value.strip())
    clean = clean.strip("._")
    return clean[:120]


def now_ts() -> int:
    return int(time.time())


def snapshot_to_json(snapshot: LimitSnapshot) -> dict[str, Any]:
    return asdict(snapshot)


def snapshot_from_json(payload: Any) -> LimitSnapshot | None:
    if not isinstance(payload, dict):
        return None

    primary = LimitWindow.from_payload(payload.get("primary"))
    secondary = LimitWindow.from_payload(payload.get("secondary"))
    fetched_at = payload.get("fetched_at", payload.get("fetchedAt"))
    if not isinstance(fetched_at, int):
        return None

    return LimitSnapshot(
        fetched_at=fetched_at,
        primary=primary,
        secondary=secondary,
        plan_type=payload.get("plan_type") if isinstance(payload.get("plan_type"), str) else None,
        reached_type=payload.get("reached_type") if isinstance(payload.get("reached_type"), str) else None,
        error=payload.get("error") if isinstance(payload.get("error"), str) else None,
    )
