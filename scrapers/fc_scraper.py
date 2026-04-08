# scrapers/fc_scraper.py
"""
Charlotte FC attendance scraper — fbref.com match logs via Playwright (avoids 403).
Falls back to structured seed data on any failure.

Usage:
    scraper = FCScraper()
    df = scraper.fetch_all_seasons([2022, 2023, 2024, 2025])
"""
import logging
import time
from io import StringIO
from typing import List

import pandas as pd

from scrapers.base_scraper import BaseScraper
from scrapers.seed_data import FC_SEED_DATA
from scrapers.raw_io import write_raw_text
from config.constants import SPORTS_SEED_ONLY
from config.settings import settings

logger = logging.getLogger(__name__)

FBREF_URL = (
    "https://fbref.com/en/squads/eb57545a/{year}/matchlogs/all_comps/schedule/"
    "Charlotte-FC-Scores-and-Fixtures-All-Competitions"
)

FC_PROMO_NIGHTS = {
    "2025-03-01": "Snapback Giveaway",
    "2025-04-05": "Foam Goalie Glove Giveaway",
    "2025-04-26": "Summer Scarf Giveaway",
    "2025-05-17": "Party Shirt Giveaway",
    "2025-05-24": "Soccer for All",
    "2025-07-05": "Straw Hat Giveaway",
    "2025-07-26": "Collectible Giveaway",
    "2025-09-13": "Inflatable Crown Giveaway",
    "2025-09-27": "Por la Cultura",
    "2025-10-18": "Fan Appreciation + T-Shirt Giveaway",
    "2024-02-24": "Patch Giveaway",
    "2024-03-23": "Women in Sports + Fanny Pack",
    "2024-04-13": "Sir Minty Cape Giveaway",
    "2024-05-04": "Star Wars Night + Lightsaber Giveaway",
    "2024-05-11": "Deck of Cards Giveaway",
    "2024-05-25": "Military Appreciation Night",
    "2024-06-15": "Pride Night + Party Shirt",
    "2024-06-19": "Juneteenth Celebration",
    "2024-08-24": "Minty Collectible Giveaway",
    "2024-09-21": "Por la Cultura + Bucket Hat",
    "2024-10-05": "Fan Appreciation + T-Shirt",
}

FC_KNOWN_ATTENDANCE = {
    "2025-03-01": 51_002,
    "2025-04-05": 29_591,
    "2025-04-26": 29_233,
    "2025-05-17": 29_755,
    "2025-05-24": 29_296,
    "2025-07-05": 28_734,
    "2025-07-26": 27_835,
    "2025-09-13": 35_607,
    "2025-09-27": 28_841,
    "2025-10-18": 31_191,
}


class FCScraper(BaseScraper):
    def _fetch_fbref_playwright(self, url: str) -> str:
        """
        Fetch fbref page using headless Chromium to reduce 403 blocks.
        Returns raw HTML string.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                )
                page = context.new_page()
                page.goto(url, wait_until="networkidle", timeout=60_000)
                page.wait_for_selector("table#matchlogs_for", timeout=20_000)
                html = page.content()
                context.close()
                return html
            finally:
                browser.close()

    def fetch_season(self, year: int) -> pd.DataFrame:
        """
        Scrape fbref via Playwright when SPORTS_SEED_ONLY is False; else seed only.
        On scrape failure, fall back to seed data.
        """
        if SPORTS_SEED_ONLY:
            logger.info("FC %s: SPORTS_SEED_ONLY — using FC_SEED_DATA (no network)", year)
            return self._from_seed(year)

        url = FBREF_URL.format(year=year)
        logger.info(f"Fetching FC season {year} from {url}")

        try:
            html = self._fetch_fbref_playwright(url)
            write_raw_text(f"charlotte_fc_{year}_fbref.html", html)
            tables = self._read_fbref_tables(html)
            df = self._parse_fbref_table(tables, year)
            logger.info(f"FC {year}: scraped {len(df)} rows from fbref")
            return df
        except Exception as e:
            logger.warning(f"fbref scrape failed for {year}: {e} — using seed data")
            return self._from_seed(year)

    def _read_fbref_tables(self, html: str) -> list:
        """Parse HTML; prefer schedule table id=matchlogs_for."""
        try:
            tables = pd.read_html(StringIO(html), attrs={"id": "matchlogs_for"}, flavor="lxml")
            if tables:
                return tables
        except ValueError:
            logger.debug("No table#matchlogs_for in HTML — falling back to largest table")
        return pd.read_html(StringIO(html), flavor="lxml")

    def fetch_all_seasons(self, years: List[int]) -> pd.DataFrame:
        try:
            frames = []
            for i, y in enumerate(years):
                if i > 0:
                    time.sleep(4)
                frames.append(self.fetch_season(y))
            frames = [f for f in frames if not f.empty]
            if not frames:
                logger.warning("FC: no rows from any season — returning empty frame")
                return pd.DataFrame()
            combined = pd.concat(frames, ignore_index=True)
            return self._enrich(combined)
        except Exception as e:
            logger.warning(f"FC fetch_all_seasons failed: {e} — using seed for requested years")
            frames = [self._from_seed(y) for y in years]
            frames = [f for f in frames if not f.empty]
            if not frames:
                return pd.DataFrame()
            return self._enrich(pd.concat(frames, ignore_index=True))

    def _parse_fbref_table(self, tables: list, year: int) -> pd.DataFrame:
        """Extract home games with attendance from fbref match log tables."""
        df = max(tables, key=len).copy()
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        if "venue" in df.columns:
            df = df[df["venue"].astype(str).str.lower().str.contains("home", na=False)].copy()

        rename = {
            "date": "date",
            "opponent": "opponent",
            "attendance": "attendance",
            "result": "result",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        if "opponent" not in df.columns:
            df["opponent"] = ""
        if "result" not in df.columns:
            df["result"] = ""
        df["team"] = "charlotte_fc"
        df["season"] = year
        df["data_source"] = "scraped_fbref"
        df["date"] = pd.to_datetime(df.get("date", pd.NaT), errors="coerce")
        df["attendance"] = (
            df.get("attendance", pd.NA)
            .astype(str)
            .str.replace(",", "", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
        )
        base_cols = ["date", "team", "season", "opponent", "attendance", "result", "data_source"]
        available = [c for c in base_cols if c in df.columns]
        return df[available].dropna(subset=["date"])

    def _from_seed(self, year: int) -> pd.DataFrame:
        """Use hardcoded seed data when scraping fails."""
        rows = FC_SEED_DATA.get(year, [])
        if not rows:
            logger.warning(f"No seed data for FC {year}")
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["team"] = "charlotte_fc"
        df["season"] = year
        df["date"] = pd.to_datetime(df["date"])
        ds_key = df["date"].dt.strftime("%Y-%m-%d")
        df["data_source"] = ds_key.map(
            lambda d: "seed_verified" if d in FC_KNOWN_ATTENDANCE else "seed_estimated"
        )
        return df

    def _enrich(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add promo flags and known attendance overrides."""
        if df.empty:
            return df
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        date_str = df["date"].dt.strftime("%Y-%m-%d")
        df["promo_name"] = date_str.map(FC_PROMO_NIGHTS).fillna("")
        df["has_promo"] = df["promo_name"].ne("").astype(int)

        df["attendance_verified"] = date_str.map(FC_KNOWN_ATTENDANCE)
        mask = df["attendance_verified"].notna()
        df.loc[mask, "attendance"] = df.loc[mask, "attendance_verified"]
        df.drop(columns=["attendance_verified"], inplace=True)

        df["day_of_week"] = df["date"].dt.day_name()
        df["is_weekend"] = df["date"].dt.dayofweek.isin([4, 5, 6]).astype(int)
        df["month"] = df["date"].dt.month
        h_default = pd.Series(19, index=df.index, dtype=float)
        if "hour" in df.columns:
            df["hour"] = pd.to_numeric(df["hour"], errors="coerce").fillna(h_default).astype(float)
        else:
            df["hour"] = h_default.astype(float)

        return df.sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    s = FCScraper()
    d = s.fetch_season(2025)
    print(d.head(10))
    print("data_source:", d["data_source"].unique() if not d.empty else [])
