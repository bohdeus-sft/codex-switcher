#!/usr/bin/env bash
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [[ -L "${SOURCE}" ]]; do
  SCRIPT_DIR="$(cd -P "$(dirname "${SOURCE}")" && pwd)"
  SOURCE="$(readlink "${SOURCE}")"
  [[ "${SOURCE}" != /* ]] && SOURCE="${SCRIPT_DIR}/${SOURCE}"
done
SCRIPT_DIR="$(cd -P "$(dirname "${SOURCE}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
FRONTEND_DIR="${PROJECT_DIR}/src/codex_switcher/frontend"
ACTION="${1:-start}"
STATE_DIR="${HOME}/.codex/codex-switcher"
BACKEND_PID_FILE="${STATE_DIR}/backend.pid"
FRONTEND_PID_FILE="${STATE_DIR}/frontend.pid"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-18765}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-15173}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}/"

BACKEND_PID=""
FRONTEND_PID=""
STARTED=0

cleanup() {
  if [[ "${STARTED}" != "1" ]]; then
    return
  fi

  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi

  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi

  rm -f "${FRONTEND_PID_FILE}" "${BACKEND_PID_FILE}"
}

trap cleanup EXIT INT TERM

usage() {
  printf 'Usage: %s [start|stop|restart|status]\n' "$(basename "$0")"
}

require_command() {
  local command_name="$1"

  if ! command -v "${command_name}" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "${command_name}" >&2
    exit 1
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local attempts="${3:-60}"

  for ((i = 1; i <= attempts; i++)); do
    if curl -fsS -o /dev/null "${url}" >/dev/null 2>&1; then
      return 0
    fi

    sleep 1
  done

  printf '%s did not become ready at %s\n' "${name}" "${url}" >&2
  exit 1
}

ensure_state_dir() {
  mkdir -p "${STATE_DIR}"
}

write_pid() {
  local pid_file="$1"
  local pid="$2"

  printf '%s\n' "${pid}" >"${pid_file}"
}

read_pid() {
  local pid_file="$1"

  if [[ -f "${pid_file}" ]]; then
    sed -n '1p' "${pid_file}"
  fi
}

is_pid_running() {
  local pid="$1"

  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

stop_pid_file() {
  local pid_file="$1"
  local name="$2"
  local pid

  pid="$(read_pid "${pid_file}")"

  if is_pid_running "${pid}"; then
    kill "${pid}" 2>/dev/null || true
    printf 'Stopped %s process %s.\n' "${name}" "${pid}"
    rm -f "${pid_file}"
    return 0
  else
    printf '%s is not running.\n' "${name}"
  fi

  rm -f "${pid_file}"
  return 1
}

stop_port() {
  local port="$1"
  local name="$2"
  local pids
  local pid
  local stopped=0

  if ! command -v lsof >/dev/null 2>&1; then
    return 1
  fi

  pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "${pids}" ]]; then
    return 1
  fi

  while IFS= read -r pid; do
    if is_pid_running "${pid}"; then
      kill "${pid}" 2>/dev/null || true
      printf 'Stopped %s listener on port %s: %s.\n' "${name}" "${port}" "${pid}"
      stopped=1
    fi
  done <<<"${pids}"

  [[ "${stopped}" == "1" ]]
}

stop_servers() {
  stop_pid_file "${FRONTEND_PID_FILE}" "Frontend" || stop_port "${FRONTEND_PORT}" "Frontend"
  stop_pid_file "${BACKEND_PID_FILE}" "Backend" || stop_port "${BACKEND_PORT}" "Backend"
}

print_status() {
  local backend_pid
  local frontend_pid

  backend_pid="$(read_pid "${BACKEND_PID_FILE}")"
  frontend_pid="$(read_pid "${FRONTEND_PID_FILE}")"

  if is_pid_running "${backend_pid}"; then
    printf 'Backend running: %s\n' "${backend_pid}"
  else
    printf 'Backend stopped.\n'
  fi

  if is_pid_running "${frontend_pid}"; then
    printf 'Frontend running: %s\n' "${frontend_pid}"
  else
    printf 'Frontend stopped.\n'
  fi
}

start_servers() {
  ensure_state_dir
  require_command curl
  require_command npm

  cd "${PROJECT_DIR}"

  if command -v uv >/dev/null 2>&1; then
    uv run python -m codex_switcher.backend.server --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" &
  elif [[ -x "${PROJECT_DIR}/.venv/bin/python" ]]; then
    PYTHONPATH="${PROJECT_DIR}/src" "${PROJECT_DIR}/.venv/bin/python" -m codex_switcher.backend.server --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" &
  else
    require_command python3
    PYTHONPATH="${PROJECT_DIR}/src" python3 -m codex_switcher.backend.server --host "${BACKEND_HOST}" --port "${BACKEND_PORT}" &
  fi
  BACKEND_PID="$!"
  write_pid "${BACKEND_PID_FILE}" "${BACKEND_PID}"

  cd "${FRONTEND_DIR}"

  if [[ ! -d node_modules ]]; then
    npm install
  fi

  VITE_API_BASE_URL="http://${BACKEND_HOST}:${BACKEND_PORT}" npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}" --strictPort &
  FRONTEND_PID="$!"
  write_pid "${FRONTEND_PID_FILE}" "${FRONTEND_PID}"
  STARTED=1

  wait_for_url "http://${BACKEND_HOST}:${BACKEND_PORT}/api/state" "Backend"
  wait_for_url "${FRONTEND_URL}" "Frontend"

  open -a Safari "${FRONTEND_URL}"

  printf 'Backend:  http://%s:%s\n' "${BACKEND_HOST}" "${BACKEND_PORT}"
  printf 'Frontend: %s\n' "${FRONTEND_URL}"
  printf 'Press Ctrl-C to stop both servers, or run %s stop.\n' "${PROJECT_DIR}/mac_neo_run.sh"

  wait
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  printf 'This launcher is intended for macOS.\n' >&2
  exit 1
fi

case "${ACTION}" in
  "start")
    start_servers
    ;;
  "stop")
    stop_servers
    ;;
  "restart")
    stop_servers
    start_servers
    ;;
  "status")
    print_status
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
