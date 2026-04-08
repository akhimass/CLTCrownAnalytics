# pipelines/event_calendar.py
"""
Charlotte competing entertainment — verified anchor events + optional web refresh.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config.settings import settings

logger = logging.getLogger(__name__)

# Tier 1 — verified / planned major draws (venue code: bofa = Bank of America Stadium)
CHARLOTTE_MAJOR_EVENTS_2026: List[Dict[str, Any]] = [
    {"date": "2026-04-18", "event": "Zach Bryan Concert", "venue": "bofa", "competition": "HIGH"},
    {"date": "2026-04-29", "event": "Bruno Mars Concert", "venue": "bofa", "competition": "HIGH"},
    {"date": "2026-05-31", "event": "USMNT vs Senegal", "venue": "bofa", "competition": "HIGH"},
    {"date": "2026-06-09", "event": "Post Malone Concert", "venue": "bofa", "competition": "HIGH"},
    {"date": "2026-06-20", "event": "Chris Stapleton Concert", "venue": "bofa", "competition": "HIGH"},
    {"date": "2026-07-29", "event": "MLS All-Star Game", "venue": "bofa", "competition": "MODERATE"},
    {"date": "2026-07-22", "event": "Charlotte FC vs Atlanta United", "venue": "bofa", "competition": "LOW"},
    {"date": "2026-08-15", "event": "Charlotte FC vs Columbus Crew", "venue": "bofa", "competition": "HIGH"},
    {"date": "2026-08-22", "event": "Charlotte FC vs DC United", "venue": "bofa", "competition": "MODERATE"},
]

_SCORE_SAME_HIGH = 0.82
_SCORE_SAME_MODERATE = 0.93
_SCORE_ADJ_HIGH = 0.97
_HANGOVER_AFTER_ALLSTAR = 0.95  # Crown Jul 30 — night after MLS All-Star Jul 29

TICKMASTER_BOFA_VENUE = "https://www.ticketmaster.com/venue/268115"


def _normalized_events() -> List[Tuple[pd.Timestamp, str, str]]:
    out = []
    for e in CHARLOTTE_MAJOR_EVENTS_2026:
        d = pd.to_datetime(e["date"]).normalize()
        lvl = str(e.get("competition", "HIGH")).upper()
        out.append((d, lvl, str(e.get("event", ""))))
    return out


def get_competition_score(date: str) -> float:
    """
    Attendance multiplier (≤1) from competing stadium events.

    - Same day HIGH: 0.82 | MODERATE: 0.93 | LOW: 1.00
    - HIGH ±1 calendar day: 0.97
    - Crown home 2026-07-30: cap at 0.95 (hangover after MLS All-Star Jul 29)
    """
    d = pd.to_datetime(date).normalize()
    events = _normalized_events()
    best = 1.0
    for ed, lvl, _name in events:
        delta = (d - ed).days
        if delta == 0:
            if lvl == "HIGH":
                best = min(best, _SCORE_SAME_HIGH)
            elif lvl == "MODERATE":
                best = min(best, _SCORE_SAME_MODERATE)
            # LOW → no suppression
        elif abs(delta) == 1 and lvl == "HIGH":
            best = min(best, _SCORE_ADJ_HIGH)

    # Night after MLS All-Star at BofA
    if d == pd.Timestamp("2026-07-30").normalize():
        best = min(best, _HANGOVER_AFTER_ALLSTAR)

    return float(best)


def competition_score_for_event_name_fragment(name: str) -> Optional[float]:
    """If `name` matches a hardcoded major event, return that date's competition score."""
    if not name or not str(name).strip():
        return None
    n = str(name).strip().lower()
    for e in CHARLOTTE_MAJOR_EVENTS_2026:
        ev = str(e.get("event", "")).lower()
        if n in ev or ev in n:
            return get_competition_score(str(e["date"]))
    return None


def get_competing_event_name(date: str) -> str:
    """Primary same-day competing event name, else hangover label for Jul 30 2026."""
    d = pd.to_datetime(date).normalize()
    if d == pd.Timestamp("2026-07-30").normalize():
        return "Night after MLS All-Star Game"
    for ed, _lvl, name in _normalized_events():
        if ed == d:
            return str(name)
    return ""


def refresh_event_calendar_from_web() -> pd.DataFrame:
    """
    Tier 2 — try to scrape Ticketmaster BofA venue page for additional titles.
    Falls back to empty frame on failure (caller merges with hardcoded list).
    """
    rows: List[Dict[str, Any]] = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; CrownAnalytics/1.0; +https://example.com)",
            "Accept": "text/html,application/xhtml+xml",
        }
        r = requests.get(TICKMASTER_BOFA_VENUE, headers=headers, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        # Heuristic: event cards often in links or headings — capture text snippets
        for a in soup.select("a[href*='event'], a[href*='/event/']"):
            t = (a.get_text() or "").strip()
            if len(t) > 8 and len(t) < 120:
                rows.append(
                    {
                        "date": "",
                        "event": t,
                        "venue": "bofa",
                        "competition": "MODERATE",
                        "source": "ticketmaster_scrape",
                    }
                )
        if not rows:
            for h in soup.find_all(["h2", "h3", "span"], class_=re.compile(r"title|event", re.I)):
                t = (h.get_text() or "").strip()
                if len(t) > 12 and len(t) < 100:
                    rows.append(
                        {
                            "date": "",
                            "event": t,
                            "venue": "bofa",
                            "competition": "LOW",
                            "source": "ticketmaster_scrape",
                        }
                    )
        logger.info("Web refresh: extracted %s candidate event strings from Ticketmaster", len(rows))
    except Exception as exc:
        logger.warning("Ticketmaster scrape failed (%s) — using hardcoded events only", exc)
    return pd.DataFrame(rows)


def build_event_calendar(save: bool = True, try_web_refresh: bool = True) -> pd.DataFrame:
    """Write competing_events.csv (hardcoded + optional scraped hints without dates)."""
    settings.ensure_dirs()
    base = pd.DataFrame(CHARLOTTE_MAJOR_EVENTS_2026)
    if try_web_refresh:
        extra = refresh_event_calendar_from_web()
        if not extra.empty:
            base = pd.concat([base, extra], ignore_index=True)
    if save:
        path = settings.DATA_PROCESSED / "competing_events.csv"
        base.to_csv(path, index=False)
        logger.info("Saved competing_events → %s", path)
    return base


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(get_competition_score("2026-06-09"), get_competing_event_name("2026-07-30"))
