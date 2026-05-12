# Codex Switcher

Rich TUI for switching Codex.app ChatGPT sessions on macOS.

## What it does

- Stores saved sessions under `~/.codex/codex-switcher/sessions`.
- Supports categories with folders, for example `sessions/work/name@example.com.json`.
- Shows all accounts in one list with category labels.
- Switches by closing Codex.app, removing `~/.codex/auth.json`, and copying the selected session into place.
- Adds accounts without calling logout: prepare a clean login, sign in inside Codex.app, then capture the new `auth.json`.
- Reads Codex rate limits slowly, one account at a time, through Codex app-server JSON-RPC using a temporary `CODEX_HOME`.

## Run

```bash
uv run codex-switcher
```

## Install command

From this repo:

```bash
uv tool install .
codex-switcher
```

For development:

```bash
uv sync
uv run codex-switcher
```
