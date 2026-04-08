# pipelines/calendar_features.py
"""
UNCC / regional academic calendar proxy + holiday weekends + move-in signals.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Set, Union

import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)

DateLike = Union[pd.Timestamp, datetime, date, str]


def _to_date(d: DateLike) -> date:
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    ts = pd.Timestamp(d)
    return ts.date()


def is_school_in_session(d: DateLike, university: str = "uncc") -> bool:
    """True when campus has meaningful in-person academic activity (score > 0)."""
    return get_school_session_score(d, university=university) > 0


def get_school_session_score(d: DateLike, university: str = "uncc") -> float:
    """
    Academic calendar intensity (update annually).

    - School year: Aug 15 – May 8 (full session = 1.0)
    - Break: May 9 – May 17 (0.0)
    - Summer session: May 18 – Aug 1 (0.4)
    - Break: Aug 2 – Aug 9 (0.05)
    - Pre-fall: Aug 10 – Aug 14 (0.2)
    - Next school year from Aug 15 (1.0)
    """
    if university != "uncc":
        logger.debug("Unknown university %s — using UNCC-style calendar", university)

    day = _to_date(d)
    y = day.year

    # Academic year ending in spring of year y: Aug 15 (y-1) → May 8 (y)
    if date(y - 1, 8, 15) <= day <= date(y, 5, 8):
        return 1.0
    # Spring–summer gap
    if date(y, 5, 9) <= day <= date(y, 5, 17):
        return 0.0
    # Summer session
    if date(y, 5, 18) <= day <= date(y, 8, 1):
        return 0.4
    # Late-summer lull
    if date(y, 8, 2) <= day <= date(y, 8, 9):
        return 0.05
    if date(y, 8, 10) <= day <= date(y, 8, 14):
        return 0.2
    # Academic year starting fall of year y: Aug 15 (y) → May 8 (y+1)
    if date(y, 8, 15) <= day <= date(y + 1, 5, 8):
        return 1.0

    return 0.0


def is_holiday_weekend(d: DateLike) -> int:
    """
    1 if game falls on Memorial Day, Independence Day, or Labor Day weekend windows.
    """
    day = _to_date(d)
    y = day.year

    def in_range(a: date, b: date) -> bool:
        return a <= day <= b

    memorial = (date(y, 5, 23), date(y, 5, 26))
    july4 = (date(y, 7, 3), date(y, 7, 6))
    labor = (date(y, 8, 29), date(y, 9, 1))
    return int(in_range(*memorial) or in_range(*july4) or in_range(*labor))


def is_move_in_weekend(d: DateLike) -> int:
    """UNCC fall move-in window — Aug 15 (Crown 2026 4pm game is a positive local signal)."""
    day = _to_date(d)
    return int(day.month == 8 and day.day == 15)


def build_calendar_features(save: bool = True) -> pd.DataFrame:
    """
    One row per unique game date (FC + Knights + Crown home), with session + holiday flags.
    """
    settings.ensure_dirs()
    dates: Set[pd.Timestamp] = set()
    for name in ("fc", "knights"):
        p = settings.DATA_PROCESSED / f"{name}_games.csv"
        if p.exists():
            df = pd.read_csv(p, parse_dates=["date"])
            for dt in df["date"].dt.normalize():
                dates.add(pd.Timestamp(dt))
    from pipelines.build_master_calendar import CROWN_FULL_SCHEDULE_2026

    for g in CROWN_FULL_SCHEDULE_2026:
        dates.add(pd.to_datetime(g["date"]).normalize())

    rows = []
    for dt in sorted(dates):
        rows.append(
            {
                "date": dt,
                "school_session_score": get_school_session_score(dt),
                "is_holiday_weekend": is_holiday_weekend(dt),
                "is_move_in_weekend": is_move_in_weekend(dt),
            }
        )
    out = pd.DataFrame(rows)
    if save and not out.empty:
        path = settings.DATA_PROCESSED / "calendar_features.csv"
        out.to_csv(path, index=False)
        logger.info("Saved calendar_features → %s (%s rows)", path, len(out))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(build_calendar_features(save=False).head())
