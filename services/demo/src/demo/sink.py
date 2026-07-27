"""A stand-in for every destination in the catalog.

Runs as a container on Squid's network with one DNS alias per catalog entry, so
Squid resolves `crm.northwind-labs.test` and connects on port 80 like any other
host. That is what keeps the demo fast and offline: throughput is bounded by
loopback, not by the room's wifi, and the access log still contains real
proxied requests to realistic hostnames.

Stdlib only — it is mounted into a plain python image, not built.
"""

from __future__ import annotations

import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 80


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _respond(self) -> None:
        # Response size varies a little so resp_bytes is not suspiciously
        # constant across thousands of events.
        body = b"x" * random.randint(400, 4000)  # noqa: S311 - cosmetic only
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._respond()

    def do_POST(self) -> None:  # noqa: N802
        # Drain the upload so the client can finish writing — this is the byte
        # count the whole demo hinges on.
        length = int(self.headers.get("Content-Length") or 0)
        remaining = length
        while remaining > 0:
            remaining -= len(self.rfile.read(min(remaining, 65536)))
        self._respond()

    do_PUT = do_POST

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def main() -> None:
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()  # noqa: S104


if __name__ == "__main__":
    main()
