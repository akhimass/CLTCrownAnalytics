# scrapers/roster_scraper.py
"""
UpShot roster pages (WordPress) — Playwright fetch; May 9+ roster drop expected.
"""
from __future__ import annotations

import argparse
import logging
import re
from typing import Dict, List, Optional

import pandas as pd
from bs4 import BeautifulSoup

from config.constants import KNOWN_STAR_PLAYERS, OPPONENT_STAR_PRESENCE
from scrapers.base_scraper import BaseScraper
from config.settings import settings

logger = logging.getLogger(__name__)

BUILDING_PHRASE = "our roster is building"


class RosterScraper(BaseScraper):
    TEAM_URLS = {
        "charlotte_crown": "https://crownupshot.com/roster/",
        "jacksonville_waves": "https://wavesupshot.com/roster/",
        "savannah_steel": "https://steelupshot.com/roster/",
        "greensboro_groove": "https://grooveupshot.com/roster/",
    }

    def _fetch_page_playwright(self, url: str) -> str:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=45_000)
                html = page.content()
                return html
            finally:
                browser.close()

    def _fetch_html(self, url: str) -> str:
        return self._fetch_page_playwright(url)

    def scrape_team_roster(self, team_key: str) -> pd.DataFrame:
        url = self.TEAM_URLS.get(team_key)
        if not url:
            return pd.DataFrame()
        try:
            html = self._fetch_html(url)
        except Exception as exc:
            logger.warning("Roster fetch failed %s: %s", url, exc)
            return pd.DataFrame()
        if BUILDING_PHRASE in html.lower():
            logger.warning("Roster still building for %s", team_key)
            return pd.DataFrame()
        return self._parse_roster_html(html, team_key)

    def _parse_roster_html(self, html: str, team_key: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "lxml")
        selectors = [
            ".player-name",
            ".roster-player",
            "h3",
            ".wp-block-heading",
            "[class*='player']",
            "[class*='roster']",
        ]
        names: List[str] = []
        for sel in selectors:
            for el in soup.select(sel):
                t = (el.get_text() or "").strip()
                t = re.sub(r"\s+", " ", t)
                if len(t) > 3 and len(t) < 80 and t.lower() not in ("roster", "players", "schedule"):
                    names.append(t)
        seen = set()
        uniq = []
        for n in names:
            if n not in seen:
                seen.add(n)
                uniq.append(n)
        if not uniq:
            return pd.DataFrame()
        rows = [{"team": team_key, "name": n, "position": "", "number": "", "background": ""} for n in uniq]
        return pd.DataFrame(rows)

    def scrape_all_rosters(self) -> pd.DataFrame:
        frames = []
        for key in self.TEAM_URLS:
            df = self.scrape_team_roster(key)
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def check_for_star_players(self, roster_df: pd.DataFrame) -> pd.DataFrame:
        if roster_df.empty:
            return roster_df
        out = roster_df.copy()

        def row_star(name: str):
            key = (name or "").strip()
            for known, meta in KNOWN_STAR_PLAYERS.items():
                if known.lower() in key.lower() or key.lower() in known.lower():
                    return True, int(meta["tier"]), meta.get("reason", "")
            return False, 0, ""

        stars = [row_star(n) for n in out["name"]]
        out["is_star"] = [s[0] for s in stars]
        out["star_tier"] = [s[1] for s in stars]
        out["star_reason"] = [s[2] for s in stars]
        return out

    def update_opponent_star_presence(self, rosters: pd.DataFrame) -> Dict[str, Dict]:
        """
        Derive opponent star flags from scraped names (does not mutate constants on disk).
        """
        out = {k: dict(v) for k, v in OPPONENT_STAR_PRESENCE.items()}
        if rosters.empty:
            return out
        team_map = {
            "jacksonville_waves": "Jacksonville Waves",
            "savannah_steel": "Savannah Steel",
            "greensboro_groove": "Greensboro Groove",
        }
        for tkey, disp in team_map.items():
            sub = rosters[rosters["team"] == tkey]
            if sub.empty:
                continue
            mx = 0
            notes = []
            for _, r in sub.iterrows():
                if r.get("is_star"):
                    mx = max(mx, int(r.get("star_tier") or 0))
                    if r.get("star_reason"):
                        notes.append(str(r["star_reason"]))
            out[disp] = {
                "has_star": mx > 0,
                "star_tier": mx,
                "notes": "; ".join(notes) if notes else "from roster scrape",
            }
        return out


def main_check():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    scraper = RosterScraper()
    try:
        df = scraper.scrape_all_rosters()
    except Exception as exc:
        logger.warning("Roster check failed: %s", exc)
        print("Rosters not yet live (May 9 announcement expected)")
        return
    if df.empty:
        print("Rosters not yet live (May 9 announcement expected)")
        return
    flagged = scraper.check_for_star_players(df)
    print(flagged.to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Print roster status or table")
    args = ap.parse_args()
    main_check()
