"""Minimal in-process metrics counters for SafeFlow.

Tracks key operational counters and exposes them via a simple JSON
summary.  Counters are thread-safe via threading.Lock.

Usage:
    from lib.metrics import counters

    counters.increment("total_jobs_created")
    counters.increment("low_confidence_jobs")
    print(counters.summary())

Expose via HTTP:
    python -m lib.metrics          # starts a tiny status endpoint on :9100
    curl http://localhost:9100/    # returns JSON counters
"""

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class MetricsCounters:
    """Thread-safe counter store."""

    # Predefined counters (auto-initialised to 0)
    _KNOWN = (
        "total_jobs_created",
        "low_confidence_jobs",
        "ai_failures",
        "sla_breaches",
        "contractor_unassigned_events",
        "ai_fallback_used",
        "media_parse_failures",
        "state_transitions",
        "escalations_triggered",
        "audit_entries_written",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {k: 0 for k in self._KNOWN}
        self._started_at = datetime.now(timezone.utc).isoformat()

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counts[name] = self._counts.get(name, 0) + amount

    def get(self, name: str) -> int:
        with self._lock:
            return self._counts.get(name, 0)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "service": "safeflow",
                "started_at": self._started_at,
                "snapshot_at": datetime.now(timezone.utc).isoformat(),
                "counters": dict(self._counts),
            }

    def reset(self) -> None:
        with self._lock:
            for k in self._counts:
                self._counts[k] = 0


# Singleton instance shared across all modules
counters = MetricsCounters()


# ---------------------------------------------------------------------------
# Tiny HTTP status endpoint
# ---------------------------------------------------------------------------

class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps(counters.summary(), indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:  # silence default logs
        pass


def serve_metrics(port: int | None = None) -> None:
    """Start a blocking HTTP server exposing /metrics on *port*."""
    port = port or int(os.environ.get("METRICS_PORT", "9100"))
    server = HTTPServer(("0.0.0.0", port), _MetricsHandler)
    print(f"SafeFlow metrics server listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    serve_metrics()
