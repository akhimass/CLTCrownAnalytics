# scrapers/seatgeek_scraper.py
"""
SeatGeek public API — optional ticket demand / performer scores (requires client_id).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from config.settings import settings
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class SeatGeekScraper(BaseScraper):
    BASE = "https://api.seatgeek.com/2"

    def __init__(self, client_id: Optional[str] = None):
        super().__init__()
        self.client_id = (client_id or settings.SEATGEEK_CLIENT_ID or "").strip()
        if not self.client_id:
            logger.warning("SeatGeekScraper: no client_id — API calls will fail")

    def get_event_listings(self, performer: str, venue_city: str = "Charlotte") -> pd.DataFrame:
        """
        Fetch current ticket listings for a performer slug in Charlotte.
        Returns: date, min_price, avg_price, listing_count, score
        """
        if not self.client_id:
            return pd.DataFrame()
        params = {
            "performers.slug": performer,
            "venue.city": venue_city,
            "client_id": self.client_id,
            "per_page": 50,
        }
        r = self.get(f"{self.BASE}/events", params=params)
        return self._parse_events(r.json())

    def _parse_events(self, data: Dict[str, Any]) -> pd.DataFrame:
        events = data.get("events") or []
        rows: List[Dict[str, Any]] = []
        for e in events:
            stats = e.get("stats") or {}
            listings = stats.get("listing_count") or stats.get("listing_count_h") or 0
            rows.append(
                {
                    "date": e.get("datetime_local", "")[:10],
                    "min_price": stats.get("lowest_price") or stats.get("lowest_sg_base_price"),
                    "avg_price": stats.get("average_price"),
                    "listing_count": listings,
                    "score": e.get("score"),
                    "short_title": e.get("short_title", ""),
                }
            )
        return pd.DataFrame(rows)

    def get_performer_score(self, performer_slug: str) -> Dict[str, Any]:
        """SeatGeek demand score for a performer (0–100 scale)."""
        if not self.client_id:
            return {"slug": performer_slug, "score": 50, "num_upcoming_events": 0}
        r = self.get(
            f"{self.BASE}/performers",
            params={"slug": performer_slug, "client_id": self.client_id},
        )
        data = r.json()
        if data.get("performers"):
            p = data["performers"][0]
            return {
                "slug": performer_slug,
                "score": p.get("score", 50),
                "num_upcoming_events": p.get("num_upcoming_events", 0),
            }
        return {"slug": performer_slug, "score": 50, "num_upcoming_events": 0}


def fetch_and_save_demand_baseline() -> pd.DataFrame:
    """Pull FC + Knights performer scores; write seatgeek_demand.csv."""
    settings.ensure_dirs()
    scraper = SeatGeekScraper()
    if not scraper.client_id:
        return pd.DataFrame()
    rows = []
    for slug in ("charlotte-fc", "charlotte-knights-baseball"):
        rows.append({"slug": slug, **scraper.get_performer_score(slug)})
    out = pd.DataFrame(rows)
    path = settings.DATA_PROCESSED / "seatgeek_demand.csv"
    out.to_csv(path, index=False)
    logger.info("Saved SeatGeek demand baseline → %s", path)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    fetch_and_save_demand_baseline()
