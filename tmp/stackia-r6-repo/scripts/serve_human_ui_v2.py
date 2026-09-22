#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from human_change_adapter import StackIAChangeAdapter, ROOT, DEFAULT_MONTH


MAX_BODY = 256 * 1024


class StackIAHandler(BaseHTTPRequestHandler):
    server_version = "StackIAHumanUI/0.1"

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:;")
        self.end_headers()
        self.wfile.write(body)

    def _same_origin_guard(self) -> bool:
        if self.headers.get("X-StackIA-Request") != "human-ui":
            self._json(403, {"status": "BLOCKED", "errors": ["missing StackIA request header"]})
            return False
        origin = self.headers.get("Origin")
        if origin:
            allowed = {
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            }
            if origin not in allowed:
                self._json(403, {"status": "BLOCKED", "errors": ["cross-origin write request rejected"]})
                return False
        return True

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"status": "BLOCKED", "errors": ["invalid Content-Length"]})
            return None
        if length <= 0 or length > MAX_BODY:
            self._json(413, {"status": "BLOCKED", "errors": ["request body is empty or too large"]})
            return None
        if "application/json" not in self.headers.get("Content-Type", ""):
            self._json(415, {"status": "BLOCKED", "errors": ["application/json required"]})
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as exc:
            self._json(400, {"status": "BLOCKED", "errors": [f"invalid JSON: {exc}"]})
            return None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            artifact = self.server.artifact_path
            if not artifact.exists():
                self._json(503, {"status": "UNAVAILABLE", "errors": [f"artifact missing: {artifact.name}"]})
                return
            self._html(artifact)
            return
        if parsed.path == "/api/status":
            self._json(
                200,
                {
                    "status": "ONLINE",
                    "mode": "validated-writeback",
                    "month": self.server.month,
                    "artifact": self.server.artifact_path.name,
                    "writeback": True,
                },
            )
            return
        self._json(404, {"status": "NOT_FOUND"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/preview", "/api/apply"):
            self._json(404, {"status": "NOT_FOUND"})
            return
        if not self._same_origin_guard():
            return
        payload = self._read_json()
        if payload is None:
            return

        try:
            if parsed.path == "/api/preview":
                change_set = payload.get("change_set", payload)
                result = self.server.adapter.preview(change_set)
                self._json(200 if result["status"] == "PREVIEW_VALID" else 422, result)
                return

            change_set = payload.get("change_set")
            preview_token = payload.get("preview_token")
            if not isinstance(change_set, dict) or not preview_token:
                self._json(400, {"status": "BLOCKED", "errors": ["change_set and preview_token are required"]})
                return
            result = self.server.adapter.apply(
                change_set,
                preview_token,
                month=self.server.month,
                rebuild=True,
            )
            self._json(200 if result["status"] == "APPLIED" else 422, result)
        except Exception as exc:
            self._json(500, {"status": "FAILED_VALIDATION", "errors": [str(exc)]})

    def log_message(self, fmt: str, *args) -> None:
        # Keep the console useful: one concise line per request.
        print(f"[StackIA] {self.address_string()} - {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve StackIA Human UI V2 with validated local writeback.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--month", default=DEFAULT_MONTH)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    if args.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("R6 server is local-only; bind to 127.0.0.1 or localhost")

    artifact = ROOT / "ui" / "prototypes" / "human-v2-r6-writeback.html"
    if not artifact.exists():
        artifact = ROOT / "ui" / "prototypes" / "human-v2-r5-full.html"

    adapter = StackIAChangeAdapter(ROOT)
    httpd = ThreadingHTTPServer((args.host, args.port), StackIAHandler)
    httpd.adapter = adapter
    httpd.month = args.month
    httpd.artifact_path = artifact

    url = f"http://127.0.0.1:{args.port}/"
    print(f"StackIA Human UI: {url}")
    print("Validated writeback is enabled. Ctrl+C stops the local server.")
    if not args.no_open:
        threading.Timer(0.35, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
