"""Centralised structured JSON logger for SafeFlow.

All scripts and services MUST use this logger to ensure consistent,
machine-parseable log output with mandatory context fields.

Usage:
    from lib.logger import get_logger

    log = get_logger("my_module")
    log.info("Job created", job_id="SF-42", facility_id="site-1")
    log.warn("Low confidence", job_id="SF-42", confidence=0.55)
    log.error("API call failed", job_id="SF-42", error="timeout")
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any


class _StructuredFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge structured context fields
        ctx: dict[str, Any] = getattr(record, "_sf_ctx", {})
        if ctx:
            entry.update(ctx)
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])
        return json.dumps(entry, default=str)


class SafeFlowLogger:
    """Thin wrapper around stdlib logging with structured context helpers.

    Guarantees every log line includes job_id, facility_id, and
    message_id when provided.
    """

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(f"safeflow.{name}")
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(_StructuredFormatter())
            self._logger.addHandler(handler)
        self._logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
        self._logger.propagate = False

    # -- public API ----------------------------------------------------------

    def info(self, message: str, **ctx: Any) -> None:
        self._emit(logging.INFO, message, ctx)

    def warn(self, message: str, **ctx: Any) -> None:
        self._emit(logging.WARNING, message, ctx)

    def error(self, message: str, exc: BaseException | None = None, **ctx: Any) -> None:
        self._emit(logging.ERROR, message, ctx, exc_info=exc)

    # -- internal ------------------------------------------------------------

    def _emit(
        self,
        level: int,
        message: str,
        ctx: dict[str, Any],
        exc_info: BaseException | None = None,
    ) -> None:
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(safeflow)",
            0,
            message,
            (),
            exc_info=(type(exc_info), exc_info, exc_info.__traceback__) if exc_info else None,
        )
        record._sf_ctx = ctx  # type: ignore[attr-defined]
        self._logger.handle(record)


def get_logger(name: str) -> SafeFlowLogger:
    """Return a SafeFlowLogger scoped to *name*."""
    return SafeFlowLogger(name)
