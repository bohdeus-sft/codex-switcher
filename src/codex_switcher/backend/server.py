from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from codex_switcher.backend.service import SwitcherService


class PrepareLoginRequest(BaseModel):
    openCodex: bool = False


class CaptureSessionRequest(BaseModel):
    email: str
    category: str = ""


class SessionKeyRequest(BaseModel):
    key: str


def create_app(
    service: SwitcherService | None = None,
    static_root: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Codex Switcher Backend")
    switcher = service or SwitcherService()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "error": str(exc.errors()[0].get("msg", "invalid request"))},
        )

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/state")
    def state() -> dict[str, Any]:
        return _call(switcher.state)

    @app.post("/api/auth/prepare-login")
    def prepare_login(payload: PrepareLoginRequest | None = None) -> dict[str, Any]:
        open_codex = payload.openCodex if payload is not None else False
        return _call(switcher.prepare_login, open_codex=open_codex)

    @app.post("/api/auth/open")
    def open_codex() -> dict[str, Any]:
        return _call(switcher.open_codex)

    @app.post("/api/auth/remove-active")
    def remove_active_auth() -> dict[str, Any]:
        return _call(switcher.remove_active_auth)

    @app.post("/api/sessions/capture")
    def capture_current(payload: CaptureSessionRequest) -> dict[str, Any]:
        if not payload.email.strip():
            raise HTTPException(status_code=400, detail="email is required")
        return _call(switcher.capture_current, payload.email.strip(), payload.category.strip())

    @app.post("/api/sessions/switch")
    def switch_to(payload: SessionKeyRequest) -> dict[str, Any]:
        return _call_with_key(switcher.switch_to, payload.key)

    @app.post("/api/sessions/refresh")
    def refresh_one(payload: SessionKeyRequest) -> dict[str, Any]:
        return _call_with_key(switcher.refresh_one, payload.key)

    @app.post("/api/sessions/refresh-all")
    def refresh_all() -> dict[str, Any]:
        return _call(switcher.refresh_all)

    @app.delete("/api/sessions/{key:path}")
    def delete_session(key: str) -> dict[str, Any]:
        return _call_with_key(switcher.delete_session, key)

    if static_root is not None:
        root = static_root.resolve()

        @app.get("/{asset_path:path}", include_in_schema=False)
        @app.head("/{asset_path:path}", include_in_schema=False)
        def serve_frontend(asset_path: str = "") -> FileResponse:
            candidate = (root / (asset_path or "index.html")).resolve()
            if root not in candidate.parents and candidate != root:
                raise HTTPException(status_code=403, detail="forbidden")
            if candidate.is_dir():
                candidate = candidate / "index.html"
            if not candidate.exists():
                candidate = root / "index.html"
            if not candidate.exists():
                raise HTTPException(status_code=404, detail="frontend build not found")
            return FileResponse(candidate)

    return app


def default_static_root() -> Path | None:
    root = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    return root if root.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Codex Switcher backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--static-root", type=Path, default=default_static_root())
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        create_app(static_root=args.static_root),
        host=args.host,
        port=args.port,
        log_level="info",
    )


def _call(function: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return function(*args, **kwargs)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'")) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _call_with_key(function: Any, key: str) -> dict[str, Any]:
    if not key.strip():
        raise HTTPException(status_code=400, detail="key is required")
    return _call(function, key.strip())


if __name__ == "__main__":
    main()
