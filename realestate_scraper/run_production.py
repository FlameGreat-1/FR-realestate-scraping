"""Production entrypoint: clean run with truncated outputs and reset checkpoint."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["--reset-checkpoint"]))
