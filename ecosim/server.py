from __future__ import annotations

import io
import json
import mimetypes
import traceback
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from ecosim.service import EcoSimService


StartResponse = Callable[[str, list[tuple[str, str]]], None]


def _json_response(start_response: StartResponse, payload: Any, status: str = "200 OK") -> list[bytes]:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ]
    start_response(status, headers)
    return [body]


def _text_response(start_response: StartResponse, payload: str, status: str = "200 OK") -> list[bytes]:
    body = payload.encode("utf-8")
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ]
    start_response(status, headers)
    return [body]


class EcoSimWSGIApp:
    def __init__(self, base_dir: Path, auto_build: bool = True) -> None:
        self.base_dir = base_dir.resolve()
        self.service = EcoSimService(self.base_dir, auto_build=auto_build)
        self.static_dir = self.base_dir / "web"
        self.extra_static_files = {
            "Frontend_Reference.jpg": self.base_dir / "Frontend_Reference.jpg",
        }

    def _parse_json_body(self, environ: dict[str, Any]) -> dict[str, Any]:
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        body = environ["wsgi.input"].read(content_length) if content_length else b""
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def _handle_api(self, method: str, path: str, environ: dict[str, Any], start_response: StartResponse) -> list[bytes]:
        query = parse_qs(environ.get("QUERY_STRING", ""))

        if method == "GET" and path == "/api/health":
            return _json_response(start_response, {"status": "ok"})

        if method == "GET" and path == "/api/config":
            return _json_response(start_response, self.service.config_payload())

        if method == "GET" and path == "/api/baseline":
            return _json_response(start_response, self.service.baseline_payload())

        if method == "GET" and path == "/api/knowledge/search":
            search_query = (query.get("q") or [""])[0]
            limit = int((query.get("limit") or ["5"])[0])
            return _json_response(start_response, self.service.knowledge_search_payload(search_query, limit))

        if method == "POST" and path == "/api/simulate":
            payload = self._parse_json_body(environ)
            return _json_response(start_response, self.service.simulate_payload(payload))

        if method == "POST" and path == "/api/compare":
            payload = self._parse_json_body(environ)
            return _json_response(start_response, self.service.compare_payload(payload))

        if method == "POST" and path == "/api/explain":
            payload = self._parse_json_body(environ)
            return _json_response(start_response, self.service.explain_payload(payload))

        if method == "POST" and path == "/api/profile-impact":
            payload = self._parse_json_body(environ)
            return _json_response(start_response, self.service.profile_impact_payload(payload))

        if method == "POST" and path == "/api/match-schemes":
            payload = self._parse_json_body(environ)
            return _json_response(start_response, self.service.scheme_match_only_payload(payload))

        if method == "POST" and path == "/api/assess":
            payload = self._parse_json_body(environ)
            return _json_response(start_response, self.service.multi_agent_assess_payload(payload))

        if method == "POST" and path == "/api/login":
            payload = self._parse_json_body(environ)
            username = payload.get("username", "")
            password = payload.get("password", "")
            return _json_response(start_response, self.service.auth.login(username, password))

        if method == "POST" and path == "/api/register":
            payload = self._parse_json_body(environ)
            username = payload.get("username", "")
            password = payload.get("password", "")
            profile = payload.get("profile", {})
            return _json_response(start_response, self.service.auth.register(username, password, profile))

        if method == "POST" and path == "/api/chat":
            payload = self._parse_json_body(environ)
            # Extract Bearer token if present
            auth_header = environ.get("HTTP_AUTHORIZATION", "")
            token = None
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            return _json_response(start_response, self.service.chat_payload(payload, token))

        return _json_response(
            start_response,
            {"error": f"Route not found: {method} {path}"},
            status="404 Not Found",
        )

    def _resolve_static_path(self, path: str) -> Path | None:
        if path in ("/", ""):
            candidate = self.static_dir / "index.html"
            return candidate if candidate.exists() else None

        requested = path.lstrip("/")
        if requested in self.extra_static_files:
            return self.extra_static_files[requested]

        candidate = (self.static_dir / requested).resolve()
        if not str(candidate).startswith(str(self.static_dir.resolve())):
            return None
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if candidate.exists():
            return candidate
        return None

    def _serve_static(self, path: str, start_response: StartResponse) -> list[bytes]:
        resolved = self._resolve_static_path(path)
        if not resolved:
            fallback = self.static_dir / "index.html"
            if fallback.exists():
                resolved = fallback
            else:
                return _json_response(start_response, {"error": "Static asset not found"}, "404 Not Found")

        body = resolved.read_bytes()
        content_type, _ = mimetypes.guess_type(str(resolved))
        headers = [
            ("Content-Type", content_type or "application/octet-stream"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ]
        start_response("200 OK", headers)
        return [body]

    def __call__(self, environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")

        try:
            if path.startswith("/api/"):
                return self._handle_api(method, path, environ, start_response)
            return self._serve_static(path, start_response)
        except Exception as exc:  # pragma: no cover - safety net
            return _json_response(
                start_response,
                {
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=5),
                },
                status="500 Internal Server Error",
            )


def create_wsgi_app(base_dir: Path, auto_build: bool = True) -> EcoSimWSGIApp:
    return EcoSimWSGIApp(base_dir, auto_build=auto_build)


def serve(base_dir: Path, host: str = "127.0.0.1", port: int = 8000, auto_build: bool = True) -> None:
    app = create_wsgi_app(base_dir, auto_build=auto_build)
    with make_server(host, port, app) as httpd:
        print(f"Serving Eco Sim on http://{host}:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping Eco Sim server.")
