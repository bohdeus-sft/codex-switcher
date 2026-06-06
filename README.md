# Codex Switcher

Local tools for switching Codex.app ChatGPT sessions on macOS.

## What it does

- Stores saved sessions under `/Users/Shared/Offline/codex-switcher/sessions`.
- Supports categories with folders, for example `sessions/work/name@example.com.json`.
- Shows all accounts in one list with category labels.
- Switches by closing Codex.app, removing `~/.codex/auth.json`, and copying the selected session into place.
- Adds accounts without calling logout: prepare a clean login, sign in inside Codex.app, then capture the new `auth.json`.
- Reads Codex rate limits slowly, one account at a time, through Codex app-server JSON-RPC using a temporary `CODEX_HOME`.

## Layout

- `src/codex_switcher/cli` contains the terminal TUI.
- `src/codex_switcher/backend` contains the local FastAPI JSON backend used by the web UI.
- `src/codex_switcher/frontend` contains the Vite React frontend.
- Shared auth/session/limit logic remains in `src/codex_switcher`.

## Run CLI

```bash
uv run codex-switcher
```

Without `uv`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=src python -m codex_switcher.cli.main
```

## Run Web UI

On macOS, start both servers and open Safari with:

```bash
./mac_neo_run.sh
```

The script can be run from any directory, uses `http://127.0.0.1:15173/` for the frontend and `http://127.0.0.1:18765/` for the backend, starts detached, writes logs under this repo's `logs/` directory, and stores PID files under `.run/`.

It also supports explicit commands, which are useful for Alfred or Spotlight app wrappers:

```bash
/Users/Shared/Offline/Python/codex-switcher/mac_neo_run.sh start
/Users/Shared/Offline/Python/codex-switcher/mac_neo_run.sh stop
/Users/Shared/Offline/Python/codex-switcher/mac_neo_run.sh restart
/Users/Shared/Offline/Python/codex-switcher/mac_neo_run.sh status
```

Start the backend:

```bash
PYTHONPATH=src python -m codex_switcher.backend.server
```

The backend listens on `http://127.0.0.1:8765` and exposes:

- `GET /api/state`
- `POST /api/auth/prepare-login`
- `POST /api/auth/remove-active`
- `POST /api/sessions/capture`
- `POST /api/sessions/switch`
- `POST /api/sessions/refresh`
- `POST /api/sessions/refresh-all`
- `DELETE /api/sessions/{key}`

Then start the frontend in another terminal:

```bash
cd src/codex_switcher/frontend
npm install
npm run dev
```

Open the local Vite URL, usually `http://127.0.0.1:5173/`. If Vite selects another local port, the frontend still calls the backend at `http://127.0.0.1:8765` in dev mode.

To serve a built frontend from the backend:

```bash
cd src/codex_switcher/frontend
npm run build
cd ../../..
PYTHONPATH=src python -m codex_switcher.backend.server
```

## Install command

From this repo:

```bash
uv tool install --reinstall .
codex-switcher
```

Use `--reinstall` after pulling or changing local code. Plain `uv tool install .` keeps the already installed tool.

For development:

```bash
uv sync
uv run codex-switcher
```
