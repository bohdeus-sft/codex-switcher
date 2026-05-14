from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from .config import Config
from .models import Session


class CodexApp:
    def __init__(self, config: Config) -> None:
        self.config = config

    def is_running(self) -> bool:
        if sys.platform != "darwin":
            return False
        result = subprocess.run(
            ["pgrep", "-x", "Codex"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0

    def wait_until_stopped(self, timeout: float = 10.0, poll_interval: float = 0.2) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.is_running():
                return True
            time.sleep(poll_interval)
        return not self.is_running()

    def stop(self) -> None:
        if sys.platform != "darwin":
            return
        if not self.is_running():
            return

        subprocess.run(
            ["osascript", "-e", 'tell application "Codex" to quit'],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if self.wait_until_stopped(timeout=8.0):
            return

        subprocess.run(
            ["pkill", "-x", "Codex"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.wait_until_stopped(timeout=3.0)

    def open(self) -> None:
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Codex"], check=False)

    def remove_active_auth(self) -> None:
        if self.config.auth_path.exists():
            self.config.auth_path.unlink()

    def switch_to(self, session: Session) -> None:
        self.stop()
        time.sleep(2)
        self.remove_active_auth()
        self._copy_auth(session.path, self.config.auth_path)
        time.sleep(2)
        self.open()

    def prepare_login(self) -> None:
        self.stop()
        time.sleep(2)
        self.remove_active_auth()

    def save_current_auth(self, destination: Path) -> None:
        if not self.config.auth_path.exists():
            raise FileNotFoundError(f"active auth file not found: {self.config.auth_path}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._copy_auth(self.config.auth_path, destination)

    @staticmethod
    def _copy_auth(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = destination.with_suffix(destination.suffix + ".tmp")
        shutil.copyfile(source, temp_path)
        temp_path.chmod(0o600)
        temp_path.replace(destination)
        destination.chmod(0o600)
