"""Command-line interface: `python -m scraper [args]`.

The CLI wraps `run_pipeline` and exposes the operational toggles that
operators actually want at runtime. All other knobs come from `.env`
via `Settings`.
"""
from __future__ import annotations

import argparse
import asyncio
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    settings = get_settings()
    log_level = args.log_level or settings.log_level
    configure_logging(level=log_level, json_format=settings.log_json)

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
