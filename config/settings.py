# config/settings.py
"""
Environment-based settings. Load with: from config.settings import settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    # Paths
    DATA_RAW      = BASE_DIR / "data" / "raw"
    DATA_PROCESSED= BASE_DIR / "data" / "processed"
    # Google Form export (Charlotte Crown / Checkers survey) — used by P12; replace file to refresh charts.
    SURVEY_RESPONSES_CSV = BASE_DIR / "data" / "raw" / "crown_survey_responses.csv"
    REPORTS_DIR   = BASE_DIR / "reports"
    MODELS_DIR    = BASE_DIR / "models" / "saved"

    # Scraping
    SCRAPE_DELAY_MIN = float(os.getenv("SCRAPE_DELAY_MIN", "1.5"))
    SCRAPE_DELAY_MAX = float(os.getenv("SCRAPE_DELAY_MAX", "3.5"))
    USER_AGENT = os.getenv(
        "USER_AGENT",
        "CrownAnalytics/1.0 (academic attendance research; contact: research@example.com)"
    )

    # Output
    EXPORT_FORMAT = os.getenv("EXPORT_FORMAT", "csv")  # csv | parquet

    # Optional third-party APIs (leave unset to skip enrichment steps)
    SEATGEEK_CLIENT_ID = os.getenv("SEATGEEK_CLIENT_ID", "").strip()

    def ensure_dirs(self):
        for d in [self.DATA_RAW, self.DATA_PROCESSED, self.REPORTS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_dirs()
