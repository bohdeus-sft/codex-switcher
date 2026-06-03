from pathlib import Path
import os
import stat
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mac_neo_run.sh"


class MacOSLauncherScriptTest(unittest.TestCase):
    def test_launcher_runs_backend_frontend_and_opens_safari(self) -> None:
        self.assertTrue(SCRIPT.exists(), "mac_neo_run.sh should exist")

        mode = os.stat(SCRIPT).st_mode
        self.assertTrue(mode & stat.S_IXUSR, "launcher should be executable")

        contents = SCRIPT.read_text()
        self.assertIn('SCRIPT_DIR="$(cd -P "$(dirname "${SOURCE}")" && pwd)"', contents)
        self.assertIn('PROJECT_DIR="${SCRIPT_DIR}"', contents)
        self.assertIn('FRONTEND_DIR="${PROJECT_DIR}/src/codex_switcher/frontend"', contents)
        self.assertIn('cd "${PROJECT_DIR}"', contents)
        self.assertIn("codex_switcher.backend.server", contents)
        self.assertIn('--host "${BACKEND_HOST}" --port "${BACKEND_PORT}"', contents)
        self.assertIn("npm run dev", contents)
        self.assertIn("BACKEND_PORT=\"${BACKEND_PORT:-18765}\"", contents)
        self.assertIn("FRONTEND_PORT=\"${FRONTEND_PORT:-15173}\"", contents)
        self.assertIn('VITE_API_BASE_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"', contents)
        self.assertIn("http://127.0.0.1:${FRONTEND_PORT}/", contents)
        self.assertIn("open -a Safari", contents)
        self.assertIn("trap cleanup EXIT INT TERM", contents)

    def test_launcher_supports_stop_restart_and_status(self) -> None:
        contents = SCRIPT.read_text()

        self.assertIn('ACTION="${1:-start}"', contents)
        self.assertIn('STATE_DIR="${HOME}/.codex/codex-switcher"', contents)
        self.assertIn('BACKEND_PID_FILE="${STATE_DIR}/backend.pid"', contents)
        self.assertIn('FRONTEND_PID_FILE="${STATE_DIR}/frontend.pid"', contents)
        self.assertIn('write_pid "${BACKEND_PID_FILE}" "${BACKEND_PID}"', contents)
        self.assertIn('write_pid "${FRONTEND_PID_FILE}" "${FRONTEND_PID}"', contents)
        self.assertIn('stop_pid_file "${FRONTEND_PID_FILE}" "Frontend"', contents)
        self.assertIn('stop_pid_file "${BACKEND_PID_FILE}" "Backend"', contents)
        self.assertIn('stop_port "${FRONTEND_PORT}" "Frontend"', contents)
        self.assertIn('stop_port "${BACKEND_PORT}" "Backend"', contents)
        self.assertIn('lsof -tiTCP:"${port}" -sTCP:LISTEN', contents)
        self.assertIn('"start")', contents)
        self.assertIn('"stop")', contents)
        self.assertIn('"restart")', contents)
        self.assertIn('"status")', contents)


if __name__ == "__main__":
    unittest.main()
