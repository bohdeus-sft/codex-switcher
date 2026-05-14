# Codex Switcher Frontend

React + Vite UI for the local Codex Switcher backend.

## Development

Start the backend from the repository root:

```bash
PYTHONPATH=src python -m codex_switcher.backend.server
```

Start the frontend:

```bash
npm install
npm run dev
```

The dev app runs at `http://127.0.0.1:5173/` and calls `http://127.0.0.1:8765/api`.

Set `VITE_API_BASE_URL` to override the backend URL.
