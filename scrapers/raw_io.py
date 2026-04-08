# scrapers/raw_io.py
"""Write fetched payloads to data/raw/ for inspection."""
from pathlib import Path

from config.settings import settings


def write_raw_text(filename: str, text: str, encoding: str = "utf-8") -> Path:
    """
    Persist raw HTML or JSON text under data/raw/.

    Args:
        filename: File name (e.g. fc_2025_fbref.html).
        text: Response body.
        encoding: File encoding.

    Returns:
        Path written.
    """
    settings.DATA_RAW.mkdir(parents=True, exist_ok=True)
    path = settings.DATA_RAW / filename
    path.write_text(text, encoding=encoding)
    return path
