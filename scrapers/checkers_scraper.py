# scrapers/checkers_scraper.py
"""
Charlotte Checkers (AHL) attendance scraper.
Source: hockeytech.com schedule API (JSON endpoint intercepted from network tab).

Usage:
    scraper = CheckersScraper()
    df = scraper.fetch_all_seasons([2022, 2023, 2024, 2025])
"""
import logging
from typing import List

import pandas as pd

from scrapers.base_scraper import BaseScraper
from scrapers.seed_data import CHECKERS_PROMOS
from scrapers.raw_io import write_raw_text
from config.settings import settings

logger = logging.getLogger(__name__)

# HockeyTech JSON API — team_id 384 = Charlotte Checkers
HOCKEYTECH_URL = (
    "https://lscluster.hockeytech.com/feed/index.php"
    "?feed=statviewfeed&view=schedule&team={team_id}&season={season_id}"
    "&month=all&location=homeaway&key=50c2cd9b5e18e390&client_code=ahl&site_id=4"
    "&league_id=35&lang=en"
)
CHECKERS_TEAM_ID = 384
SEASON_IDS = {
    2022: 68, 2023: 72, 2024: 76, 2025: 80,  # AHL season IDs — verify on site
}

CHECKERS_PROMOS_LOOKUP = {
    # 2025-26 confirmed promo nights
    "2025-11-07": "Military Appreciation Night",
    "2025-11-08": "Checkers-chella",
    "2025-12-20": "Throwback Jerseys",
    "2026-01-13": "$1 Ticket Night",
    "2026-01-31": "Autism Awareness Night",
    "2026-02-06": "First Responders Night",
    "2026-02-07": "Olympic Themed Jerseys",
    "2026-02-15": "Stick it to Cancer Night",
    "2026-03-14": "St. Patty's Day Jerseys",
    "2026-04-11": "Pooch Party",
}


class CheckersScraper(BaseScraper):
    def fetch_season(self, year: int) -> pd.DataFrame:
        season_id = SEASON_IDS.get(year)
        if not season_id:
            logger.warning(f"No season ID for Checkers {year}")
            return pd.DataFrame()

        url = HOCKEYTECH_URL.format(team_id=CHECKERS_TEAM_ID, season_id=season_id)
        logger.info(f"Fetching Checkers {year} (season {season_id})")

        try:
            r = self.get(url)
            write_raw_text(f"charlotte_checkers_{year}_hockeytech.json", r.text)
            try:
                data = r.json()
            except ValueError as je:
                logger.warning(f"HockeyTech body not JSON for {year}: {je} — returning empty")
                return pd.DataFrame()
            return self._parse_json(data, year)
        except Exception as e:
            logger.warning(f"HockeyTech failed for {year}: {e} — returning empty")
            return pd.DataFrame()

    def fetch_all_seasons(self, years: List[int]) -> pd.DataFrame:
        try:
            frames = [self.fetch_season(y) for y in years]
            frames = [f for f in frames if not f.empty]
            if not frames:
                return pd.DataFrame()
            combined = pd.concat(frames, ignore_index=True)
            return self._enrich(combined)
        except Exception as e:
            logger.warning(f"Checkers fetch_all_seasons failed: {e} — returning empty")
            return pd.DataFrame()

    def _parse_json(self, data: dict, year: int) -> pd.DataFrame:
        """
        HockeyTech JSON structure (inspect actual response to confirm keys):
        data -> SectionList -> [...] -> rows -> [...] -> row -> {...game fields...}
        """
        rows = []
        try:
            sections = data.get("SectionList", [])
            for section in sections:
                for row_group in section.get("rows", []):
                    for game in row_group.get("row", []):
                        if game.get("home_team_id") == str(CHECKERS_TEAM_ID):
                            rows.append({
                                "date": game.get("date_with_day", ""),
                                "opponent": game.get("visiting_team_name", ""),
                                "attendance": game.get("attendance", None),
                                "result": game.get("game_status", ""),
                                "team": "charlotte_checkers",
                                "season": year,
                            })
        except Exception as e:
            logger.warning(f"Checkers JSON parse error for season {year}: {e}")

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["attendance"] = pd.to_numeric(df["attendance"], errors="coerce")
        return df.dropna(subset=["date"])

    def _enrich(self, df: pd.DataFrame) -> pd.DataFrame:
        date_str = df["date"].dt.strftime("%Y-%m-%d")
        df["promo_name"] = date_str.map(CHECKERS_PROMOS_LOOKUP).fillna("")
        df["has_promo"] = df["promo_name"].ne("").astype(int)
        df["day_of_week"] = df["date"].dt.day_name()
        df["is_weekend"] = df["date"].dt.dayofweek.isin([4, 5, 6]).astype(int)
        df["month"] = df["date"].dt.month
        return df.sort_values("date").reset_index(drop=True)
