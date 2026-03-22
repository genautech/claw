#!/usr/bin/env python3
"""
ArbitrageNinja Dashboard Server

Simple HTTP server that:
  1. Serves the ninja-dashboard.html page
  2. Serves ninja_trades.jsonl data via /data/ninja_trades.jsonl
  3. Provides /api/ninja/trades JSON endpoint

Usage:
    python3 scripts/serve-ninja-dashboard.py [--port 8765]
"""

import http.server
import json
import os
import sys
from pathlib import Path
import argparse

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
DASHBOARD_DIR = PROJECT_ROOT / "dashboard-web"
DATA_DIR = PROJECT_ROOT / "data"
NINJA_LOG = DATA_DIR / "ninja_trades.jsonl"


class NinjaDashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler that serves dashboard files and ninja data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        # Root → serve ninja-dashboard.html
        if self.path == "/" or self.path == "":
            self.path = "/ninja-dashboard.html"
            return super().do_GET()

        # Serve JSONL data
        if self.path == "/data/ninja_trades.jsonl":
            self._serve_jsonl()
            return

        # JSON API endpoint
        if self.path == "/api/ninja/trades":
            self._serve_json_api()
            return

        # Serve static files from dashboard-web
        return super().do_GET()

    def _serve_jsonl(self):
        """Serve the raw JSONL file."""
        if not NINJA_LOG.exists():
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"No trade data yet.")
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(NINJA_LOG, "rb") as f:
            self.wfile.write(f.read())

    def _serve_json_api(self):
        """Serve trades as a JSON array."""
        trades = []
        if NINJA_LOG.exists():
            with open(NINJA_LOG, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            trades.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(trades, indent=2).encode())

    def end_headers(self):
        # Add CORS headers to all responses
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        super().end_headers()

    def log_message(self, format, *args):
        # Color the log output
        msg = format % args
        if "200" in msg:
            print(f"  ✅ {msg}")
        elif "404" in msg:
            print(f"  ⚠️  {msg}")
        else:
            print(f"  📡 {msg}")


def main():
    parser = argparse.ArgumentParser(description="ArbitrageNinja Dashboard Server")
    parser.add_argument("--port", type=int, default=8765, help="Port to serve on (default: 8765)")
    args = parser.parse_args()

    print("=" * 60)
    print("  🥷 ArbitrageNinja Dashboard Server")
    print("=" * 60)
    print(f"  📂 Serving: {DASHBOARD_DIR}")
    print(f"  📊 Data:    {NINJA_LOG}")
    print(f"  🌐 URL:     http://localhost:{args.port}")
    print(f"  📋 API:     http://localhost:{args.port}/api/ninja/trades")
    print("=" * 60)

    server = http.server.HTTPServer(("0.0.0.0", args.port), NinjaDashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
