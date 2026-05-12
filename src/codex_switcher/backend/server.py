from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .service import SwitcherService

API_PREFIX = "/api"


class SwitcherRequestHandler(BaseHTTPRequestHandler):
    service: SwitcherService
    static_root: Path | None = None

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/health":
                self._send_json({"ok": True})
            elif parsed.path == "/api/state":
                self._send_json(self.service.state())
            elif parsed.path.startswith(API_PREFIX):
                self._send_error(HTTPStatus.NOT_FOUND, "endpoint not found")
            else:
                self._serve_static(parsed.path)
        except Exception as exc:
            self._send_exception(exc)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/health":
                self._send_json({"ok": True}, head_only=True)
            elif parsed.path == "/api/state":
                self._send_json(self.service.state(), head_only=True)
            elif parsed.path.startswith(API_PREFIX):
                self._send_error(HTTPStatus.NOT_FOUND, "endpoint not found", head_only=True)
            else:
                self._serve_static(parsed.path, head_only=True)
        except Exception as exc:
            self._send_exception(exc)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/auth/prepare-login":
                self._send_json(self.service.prepare_login(open_codex=bool(payload.get("openCodex"))))
            elif parsed.path == "/api/auth/open":
                self._send_json(self.service.open_codex())
            elif parsed.path == "/api/auth/remove-active":
                self._send_json(self.service.remove_active_auth())
            elif parsed.path == "/api/sessions/capture":
                self._send_json(
                    self.service.capture_current(
                        email=_required_str(payload, "email"),
                        category=_optional_str(payload, "category"),
                    )
                )
            elif parsed.path == "/api/sessions/switch":
                self._send_json(self.service.switch_to(_required_str(payload, "key")))
            elif parsed.path == "/api/sessions/refresh":
                self._send_json(self.service.refresh_one(_required_str(payload, "key")))
            elif parsed.path == "/api/sessions/refresh-all":
                self._send_json(self.service.refresh_all())
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "endpoint not found")
        except Exception as exc:
            self._send_exception(exc)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/sessions/"):
                key = unquote(parsed.path.removeprefix("/api/sessions/"))
                self._send_json(self.service.delete_session(key))
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "endpoint not found")
        except Exception as exc:
            self._send_exception(exc)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _serve_static(self, request_path: str, head_only: bool = False) -> None:
        if self.static_root is None:
            self._send_error(HTTPStatus.NOT_FOUND, "static frontend not configured")
            return

        clean_path = unquote(request_path).lstrip("/") or "index.html"
        candidate = (self.static_root / clean_path).resolve()
        static_root = self.static_root.resolve()
        if static_root not in candidate.parents and candidate != static_root:
            self._send_error(HTTPStatus.FORBIDDEN, "forbidden")
            return
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.exists() and not request_path.startswith(API_PREFIX):
            candidate = static_root / "index.html"
        if not candidate.exists():
            self._send_error(HTTPStatus.NOT_FOUND, "file not found")
            return

        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_common_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_json(
        self,
        payload: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        head_only: bool = False,
    ) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str, head_only: bool = False) -> None:
        self._send_json({"ok": False, "error": message}, status, head_only=head_only)

    def _send_exception(self, exc: Exception) -> None:
        if isinstance(exc, KeyError):
            self._send_error(HTTPStatus.NOT_FOUND, str(exc).strip("'"))
        elif isinstance(exc, (ValueError, FileNotFoundError)):
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        else:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    static_root: Path | None = None,
    service: SwitcherService | None = None,
) -> ThreadingHTTPServer:
    class Handler(SwitcherRequestHandler):
        pass

    Handler.service = service or SwitcherService()
    Handler.static_root = static_root
    return ThreadingHTTPServer((host, port), Handler)


def default_static_root() -> Path | None:
    root = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    return root if root.exists() else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Codex Switcher backend.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--static-root", type=Path, default=default_static_root())
    args = parser.parse_args()

    server = create_server(args.host, args.port, args.static_root)
    print(f"Codex Switcher backend listening on http://{args.host}:{args.port}")
    if args.static_root:
        print(f"Serving frontend from {args.static_root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _optional_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


if __name__ == "__main__":
    main()
