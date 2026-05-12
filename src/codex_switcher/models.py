from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Session:
    email: str
    category: str
    path: Path
    fingerprint: str
    active: bool = False

    @property
    def display_category(self) -> str:
        return self.category or "default"

    @property
    def key(self) -> str:
        return f"{self.category}/{self.email}" if self.category else self.email


@dataclass(frozen=True)
class LimitWindow:
    used_percent: float | None
    window_duration_mins: int | None
    resets_at: int | None

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "LimitWindow | None":
        if not payload:
            return None
        return cls(
            used_percent=_as_float(_first_present(payload, "usedPercent", "used_percent")),
            window_duration_mins=_as_int(_first_present(payload, "windowDurationMins", "window_duration_mins")),
            resets_at=_as_int(_first_present(payload, "resetsAt", "resets_at", "resetAt", "reset_at")),
        )


@dataclass(frozen=True)
class LimitSnapshot:
    fetched_at: int
    primary: LimitWindow | None
    secondary: LimitWindow | None
    plan_type: str | None
    reached_type: str | None
    error: str | None = None

    @classmethod
    def error_snapshot(cls, fetched_at: int, message: str) -> "LimitSnapshot":
        return cls(
            fetched_at=fetched_at,
            primary=None,
            secondary=None,
            plan_type=None,
            reached_type=None,
            error=message,
        )


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None
