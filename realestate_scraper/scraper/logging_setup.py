"""Structured logging bootstrap.

A single `configure_logging` call from the entrypoint is enough; every
other module obtains a logger via `logging.getLogger(__name__)` and gets
the same configuration for free.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

_CONFIGURED = False

# Asyncio messages we deliberately suppress. These come from chromium
# subprocess pipes that asyncio's BaseProtocol catches when a context
# is cancelled mid-borrow. They are cosmetic, but at hundreds per
# cancellation cascade they slow the loop with stderr writes.
_SUPPRESSED_ASYNCIO_MSG_FRAGMENTS = (
    "pipe closed by peer",
    "os.write(pipe, data) raised exception",
)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in payload or key.startswith("_"):
                continue
            if key in (
                "args", "msg", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno",
                "funcName", "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "name", "taskName",
            ):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", json_format: bool = False) -> None:
    """Idempotently configure the root logger for the whole process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    if json_format:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Tame noisy third-party loggers.
    for noisy in ("httpx", "httpcore", "hpack", "asyncio", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Filter the chromium-pipe-close cascade out of the asyncio logger.
    # We attach a Filter rather than installing a loop exception handler
    # because the messages come through `logging.getLogger('asyncio')`
    # at WARNING level, not via loop.set_exception_handler.
    logging.getLogger("asyncio").addFilter(_AsyncioPipeNoiseFilter())

    _CONFIGURED = True


class _AsyncioPipeNoiseFilter(logging.Filter):
    """Drop chromium-driver pipe-close warnings from asyncio.

    Returns False (suppress) only when the message contains one of
    the known-cosmetic fragments. Every other asyncio warning passes
    through unchanged so we never hide a real defect.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        message = record.getMessage()
        for fragment in _SUPPRESSED_ASYNCIO_MSG_FRAGMENTS:
            if fragment in message:
                return False
        return True


# Re-export so tests / external callers can construct or extend it.
__all__ = ["configure_logging", "_AsyncioPipeNoiseFilter"]


_ = asyncio  # imported for module-level side-effect compat; do not remove
