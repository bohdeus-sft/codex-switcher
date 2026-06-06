from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    codex_home: Path
    switcher_home: Path
    sessions_dir: Path
    auth_path: Path
    cache_path: Path
    codex_binary: Path
    legacy_switcher_homes: tuple[Path, ...] = field(default_factory=tuple)
    refresh_delay_seconds: int = 15

    @classmethod
    def load(cls) -> "Config":
        codex_home = Path.home() / ".codex"
        switcher_home = Path("/Users/Shared/Offline/codex-switcher")
        return cls(
            codex_home=codex_home,
            switcher_home=switcher_home,
            sessions_dir=switcher_home / "sessions",
            auth_path=codex_home / "auth.json",
            cache_path=switcher_home / "limits-cache.json",
            codex_binary=Path("/Applications/Codex.app/Contents/Resources/codex"),
            legacy_switcher_homes=(codex_home / "codex-switcher",),
        )

    def ensure_dirs(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
