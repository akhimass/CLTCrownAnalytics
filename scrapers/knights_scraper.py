# scrapers/knights_scraper.py
"""
Charlotte Knights attendance scraper.
Primary: thebaseballcube.com game logs (HTML tables, pandas-parseable).

Usage:
    scraper = KnightsScraper()
    df = scraper.fetch_all_seasons([2022, 2023, 2024, 2025])
"""
import logging
from io import StringIO
from typing import List

import pandas as pd

from scrapers.base_scraper import BaseScraper
from scrapers.seed_data import KNIGHTS_SEED_DATA, KNIGHTS_PROMOS
from scrapers.raw_io import write_raw_text
from config.constants import SPORTS_SEED_ONLY
from config.settings import settings

logger = logging.getLogger(__name__)

BASEBALL_CUBE_IDS = {
    2022: "2022~14021",
    2023: "2023~14021",
    2024: "2024~14021",
    2025: "2025~14021",
}
BASEBALL_CUBE_BASE = "https://www.thebaseballcube.com/content/minor_game_log"

KNIGHTS_RECURRING_PROMOS = {
    "friday":    "Friday Night Fireworks",
    "wednesday": "Bark in the Ballpark",
    "thursday":  "Thirsty Thursday",
}


class KnightsScraper(BaseScraper):
    def fetch_season(self, year: int) -> pd.DataFrame:
        if SPORTS_SEED_ONLY:
            logger.info("Knights %s: SPORTS_SEED_ONLY — using KNIGHTS_SEED_DATA (no network)", year)
            return self._from_seed(year)

        season_id = BASEBALL_CUBE_IDS.get(year)
        if not season_id:
            logger.warning(f"No Baseball Cube ID for Knights {year} — using seed data")
            return self._from_seed(year)

        url = f"{BASEBALL_CUBE_BASE}/{season_id}/"
        logger.info(f"Fetching Knights {year} from {url}")

        try:
            r = self.get(url)
            write_raw_text(f"charlotte_knights_{year}_thebaseballcube.html", r.text)
            tables = pd.read_html(StringIO(r.text))
            df = self._parse_cube_table(tables, year)
            logger.info(f"Knights {year}: scraped {len(df)} rows")
            return df
        except Exception as e:
            logger.warning(f"thebaseballcube failed for {year}: {e} — using seed data")
            return self._from_seed(year)

    def fetch_all_seasons(self, years: List[int]) -> pd.DataFrame:
        try:
            frames = [self.fetch_season(y) for y in years]
            frames = [f for f in frames if not f.empty]
            if not frames:
                logger.warning("Knights: no rows from any season — using seed for requested years")
                frames = [self._from_seed(y) for y in years]
                frames = [f for f in frames if not f.empty]
                if not frames:
                    return pd.DataFrame()
                return self._enrich(pd.concat(frames, ignore_index=True))
            combined = pd.concat(frames, ignore_index=True)
            return self._enrich(combined)
        except Exception as e:
            logger.warning(f"Knights fetch_all_seasons failed: {e} — using seed for requested years")
            frames = [self._from_seed(y) for y in years]
            frames = [f for f in frames if not f.empty]
            if not frames:
                return pd.DataFrame()
            return self._enrich(pd.concat(frames, ignore_index=True))

    def _parse_cube_table(self, tables: list, year: int) -> pd.DataFrame:
        """Normalize thebaseballcube game log (handles multi-index headers)."""
        for i, t in enumerate(tables):
            logger.debug("Table %s: %s", i, list(t.columns)[:12])

        df = max(tables, key=len).copy()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ["_".join(str(c) for c in col if str(c) != "nan").strip("_") for col in df.columns]

        df.columns = [
            str(c).lower().strip().replace(" ", "_").replace("/", "_") for c in df.columns
        ]
        logger.info("thebaseballcube columns: %s", list(df.columns))

        home_col = next(
            (c for c in df.columns if c in ("h_a", "ha", "home_away", "h_a_")),
            None,
        )
        if home_col:
            df = df[df[home_col].astype(str).str.upper().isin(("H", "HOME"))].copy()
        else:
            logger.warning("Could not find home/away column — using all games")

        att_col = next((c for c in df.columns if "att" in c.lower()), None)
        if att_col:
            df = df.rename(columns={att_col: "attendance"})

        date_col = next((c for c in df.columns if "date" in c.lower()), None)
        if date_col:
            df = df.rename(columns={date_col: "date"})

        opp_col = next((c for c in df.columns if "opp" in c.lower()), None)
        if opp_col:
            df = df.rename(columns={opp_col: "opponent"})

        wl_col = next(
            (c for c in df.columns if c in ("w_l", "w_l_") or (isinstance(c, str) and "w_l" in c)),
            None,
        )
        if wl_col:
            df = df.rename(columns={wl_col: "result"})

        df["team"] = "charlotte_knights"
        df["season"] = year
        df["data_source"] = "scraped_baseball_cube"
        df["date"] = pd.to_datetime(df.get("date", pd.NaT), errors="coerce")
        att = df.get("attendance", pd.Series(dtype=float))
        df["attendance"] = pd.to_numeric(
            att.astype(str).str.replace(",", "", regex=False).str.replace("--", "", regex=False),
            errors="coerce",
        )
        if "result" not in df.columns:
            df["result"] = ""

        cols = [c for c in ["date", "team", "season", "opponent", "attendance", "result", "data_source"] if c in df.columns]
        return df[cols].dropna(subset=["date"])

    def _from_seed(self, year: int) -> pd.DataFrame:
        rows = KNIGHTS_SEED_DATA.get(year, [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["team"] = "charlotte_knights"
        df["season"] = year
        df["date"] = pd.to_datetime(df["date"])
        df["data_source"] = "seed_estimated"
        return df

    def _enrich(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add promo flags, recurring-event tags, and time features."""
        if df.empty:
            return df
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        date_str = df["date"].dt.strftime("%Y-%m-%d")
        df["day_of_week"] = df["date"].dt.day_name()
        df["is_weekend"] = df["date"].dt.dayofweek.isin([4, 5, 6]).astype(int)
        df["month"] = df["date"].dt.month

        df["promo_name"] = date_str.map(KNIGHTS_PROMOS).fillna("")

        for day, promo in KNIGHTS_RECURRING_PROMOS.items():
            mask = (df["day_of_week"].str.lower() == day) & (df["promo_name"] == "")
            df.loc[mask, "promo_name"] = promo

        df["has_promo"] = df["promo_name"].ne("").astype(int)
        h_default = df["day_of_week"].map({
            "Friday": 19, "Saturday": 18, "Sunday": 13,
        }).fillna(18)
        if "hour" in df.columns:
            df["hour"] = pd.to_numeric(df["hour"], errors="coerce").fillna(h_default).astype(float)
        else:
            df["hour"] = h_default.astype(float)

        return df.sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    s = KnightsScraper()
    d = s.fetch_season(2025)
    print(d.head(10))
    print("columns:", list(d.columns))
