from pathlib import Path
import os


INPUT_CSV_NAME = "FR_realestate_scraping - FR 140 (1).csv"


def resolve_input_csv_path() -> Path:
    """Resolve the client input CSV using env overrides and documented fallbacks."""
    env_path = os.getenv("CSV_PATH")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return candidate

    repo_root = Path(__file__).resolve().parents[1]
    fallbacks = [
        repo_root.parent / INPUT_CSV_NAME,
        repo_root / INPUT_CSV_NAME,
        repo_root / "docs" / INPUT_CSV_NAME,
    ]
    for candidate in fallbacks:
        if candidate.exists():
            return candidate

    # Preserve the documented default when no file is found.
    return fallbacks[0]
