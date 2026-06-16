"""
serve.py — Preview phase: serve index.html at localhost:8000.

Spawned as a detached background process by supervisor.py when entering
PREVIEW state. Runs until killed (supervisor sends SIGTERM via the PID stored
in .tmp/preview_server.pid when the user runs `advance preview`).

Can also be run directly for testing:
  python execution/serve.py
"""
from __future__ import annotations

import http.server
import os
import sys
import webbrowser
from pathlib import Path

PORT = 8000
ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    os.chdir(str(ROOT))  # serve from project root so css/ js/ assets/ resolve correctly
    handler = http.server.SimpleHTTPRequestHandler
    handler.log_message = lambda *a: None  # suppress per-request noise in background

    with http.server.HTTPServer(("", PORT), handler) as httpd:
        url = f"http://localhost:{PORT}/"
        print(f"[serve.py] Preview running at {url}", flush=True)
        print(f"[serve.py] Edit files freely. When done:", flush=True)
        print(f"[serve.py]   python execution/supervisor.py advance preview", flush=True)
        webbrowser.open(url)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
