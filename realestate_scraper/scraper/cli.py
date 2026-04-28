"""Command-line interface: `python -m scraper [args]`.

The CLI wraps `run_pipeline` and exposes the operational toggles that
operators actually want at runtime. All other knobs come from `.env`
via `Settings`.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from typing import Sequence

from .config import get_settings
from .logging_setup import configure_logging
from .pipeline import run_pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scraper",
        description="Scalable real estate listing scraper.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of domains to process this run.",
    )
    parser.add_argument(
        "--keep-outputs",
        action="store_true",
        help="Append to existing output CSVs instead of truncating.",
    )
    parser.add_argument(
        "--reset-checkpoint",
        action="store_true",
        help="Wipe the resume checkpoint before starting.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override LOG_LEVEL (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser


def _install_hard_exit_on_second_signal() -> None:
    """On POSIX, make a second Ctrl-C exit the process immediately.

    asyncio.run handles the first SIGINT by raising CancelledError
    into every coroutine and unwinding cleanly. That unwind has to
    talk to the chromium driver, the httpx pool, and any in-flight
    threads - all of which can hang for tens of seconds during a
    crash. A second Ctrl-C should bypass that and kill the process
    outright. We do NOT replace the first handler: asyncio still
    needs it for graceful cancellation.
    """
    if os.name != "posix":
        return
    state = {"hits": 0}
    default_handler = signal.getsignal(signal.SIGINT)

    def _handler(signum, frame):  # type: ignore[no-untyped-def]
        state["hits"] += 1
        if state["hits"] >= 2:
            # Hard exit. os._exit skips atexit and finalisers, which
            # is exactly what we want when the loop is wedged on a
            # dying subprocess pipe.
            os._exit(130)
        # First hit: defer to whatever handler was installed (asyncio
        # installs its own once the loop starts).
        if callable(default_handler):
            try:
                default_handler(signum, frame)
            except KeyboardInterrupt:
                raise

    try:
        signal.signal(signal.SIGINT, _handler)
    except (ValueError, OSError):
        # Not running in the main thread, e.g. under pytest. Skip.
        pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    settings = get_settings()
    log_level = args.log_level or settings.log_level
    configure_logging(level=log_level, json_format=settings.log_json)

    _install_hard_exit_on_second_signal()

    try:
        asyncio.run(
            run_pipeline(
                limit=args.limit,
                truncate_outputs=not args.keep_outputs,
                reset_checkpoint=args.reset_checkpoint,
            )
        )
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
