# pipelines/weather_features.py
"""
Historical game-day weather for Charlotte (Open-Meteo archive, no API key).
Writes data/processed/game_weather.csv
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import List, Optional, Set

import pandas as pd
import requests

from config.settings import settings

logger = logging.getLogger(__name__)

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
LAT, LON = 35.2271, -80.8431
REQUEST_DELAY_S = 0.5

# Crown 2026 forward-looking defaults (scenario baseline; simulator can override)
CROWN_DEFAULT_TEMP_MAX_F = 88.0
CROWN_DEFAULT_TEMP_MIN_F = 70.0  # plausible night low for summer evening games
CROWN_DEFAULT_PRECIP_IN = 0.15
CROWN_DEFAULT_WIND_MPH = 8.0


def _c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def _mm_to_in(mm: float) -> float:
    return mm / 25.4


def _kmh_to_mph(kmh: float) -> float:
    return kmh / 1.60934


def _derive_flags(temp_max_f: float, precip_in: float) -> tuple:
    is_rainy = int(precip_in > 0.1)
    is_hot_day = int(temp_max_f > 90)
    is_bad = int(precip_in > 0.1 or temp_max_f > 95 or temp_max_f < 35)
    return is_bad, is_hot_day, is_rainy


def _fetch_year_daily(year: int, start_d: date, end_d: date) -> pd.DataFrame:
    """Single archive request for [start_d, end_d] inclusive."""
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
        "timezone": "America/New_York",
    }
    r = requests.get(OPEN_METEO_ARCHIVE, params=params, timeout=60)
    r.raise_for_status()
    j = r.json()
    daily = j.get("daily") or {}
    times = daily.get("time") or []
    if not times:
        return pd.DataFrame()
    tmax = daily.get("temperature_2m_max") or [None] * len(times)
    tmin = daily.get("temperature_2m_min") or [None] * len(times)
    prcp = daily.get("precipitation_sum") or [0.0] * len(times)
    wind = daily.get("windspeed_10m_max") or [0.0] * len(times)

    rows = []
    for i, t in enumerate(times):
        d = pd.to_datetime(t).date()
        c_max = float(tmax[i]) if tmax[i] is not None else float("nan")
        c_min = float(tmin[i]) if tmin[i] is not None else float("nan")
        mm = float(prcp[i] or 0)
        wk = float(wind[i] or 0)
        tmax_f = _c_to_f(c_max) if pd.notna(c_max) else float("nan")
        tmin_f = _c_to_f(c_min) if pd.notna(c_min) else float("nan")
        pin = _mm_to_in(mm)
        wmph = _kmh_to_mph(wk)
        bad, hot, rain = _derive_flags(tmax_f, pin)
        rows.append(
            {
                "date": pd.Timestamp(d),
                "temp_max_f": tmax_f,
                "temp_min_f": tmin_f,
                "precipitation_inches": pin,
                "windspeed_mph": wmph,
                "is_bad_weather": bad,
                "is_hot_day": hot,
                "is_rainy": rain,
            }
        )
    return pd.DataFrame(rows)


def _collect_game_dates() -> Set[pd.Timestamp]:
    dates: Set[pd.Timestamp] = set()
    for name in ("fc", "knights"):
        p = settings.DATA_PROCESSED / f"{name}_games.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, parse_dates=["date"])
        for d in df["date"].dt.normalize():
            dates.add(pd.Timestamp(d))
    return dates


def _crown_2026_dates() -> Set[pd.Timestamp]:
    from pipelines.build_master_calendar import CROWN_FULL_SCHEDULE_2026

    out: Set[pd.Timestamp] = set()
    for g in CROWN_FULL_SCHEDULE_2026:
        out.add(pd.to_datetime(g["date"]).normalize())
    return out


def _rows_for_crown_future(ds: pd.Timestamp) -> dict:
    """Synthetic summer baseline; is_bad_weather / is_hot_day / is_rainy set to 0 per spec."""
    return {
        "date": ds,
        "temp_max_f": CROWN_DEFAULT_TEMP_MAX_F,
        "temp_min_f": CROWN_DEFAULT_TEMP_MIN_F,
        "precipitation_inches": CROWN_DEFAULT_PRECIP_IN,
        "windspeed_mph": CROWN_DEFAULT_WIND_MPH,
        "is_bad_weather": 0,
        "is_hot_day": 0,
        "is_rainy": 0,
    }


def write_zero_weather_fallback() -> pd.DataFrame:
    """All-zero weather rows for every known game date (Open-Meteo unreachable)."""
    settings.ensure_dirs()
    game_dates = sorted(_collect_game_dates() | _crown_2026_dates())
    rows = []
    for d in game_dates:
        rows.append(
            {
                "date": pd.Timestamp(d).normalize(),
                "temp_max_f": 0.0,
                "temp_min_f": 0.0,
                "precipitation_inches": 0.0,
                "windspeed_mph": 0.0,
                "is_bad_weather": 0,
                "is_hot_day": 0,
                "is_rainy": 0,
            }
        )
    out = pd.DataFrame(rows)
    path = settings.DATA_PROCESSED / "game_weather.csv"
    out.to_csv(path, index=False)
    logger.warning("Wrote zeroed weather fallback → %s (%s rows)", path, len(out))
    return out


def fetch_game_weather(
    dry_run: bool = False,
    save: bool = True,
) -> pd.DataFrame:
    """
    Build game_weather.csv for all unique dates in fc_games + knights_games,
    plus Crown 2026 season dates (home + road; synthetic weather baseline).

    Args:
        dry_run: If True, skip HTTP; return plausible rows for collected dates only.
        save: Write CSV to data/processed/game_weather.csv when True.
    """
    settings.ensure_dirs()
    game_dates = _collect_game_dates()
    crown_dates = _crown_2026_dates()
    all_dates = sorted(game_dates | crown_dates)
    if not all_dates:
        logger.warning("No game dates found — writing empty weather frame")
        empty = pd.DataFrame(
            columns=[
                "date",
                "temp_max_f",
                "temp_min_f",
                "precipitation_inches",
                "windspeed_mph",
                "is_bad_weather",
                "is_hot_day",
                "is_rainy",
            ]
        )
        if save:
            empty.to_csv(settings.DATA_PROCESSED / "game_weather.csv", index=False)
        return empty

    today = pd.Timestamp.now(tz=None).normalize()
    historical_dates: List[pd.Timestamp] = []
    future_crown: List[pd.Timestamp] = []
    for d in all_dates:
        dn = pd.Timestamp(d).normalize()
        if dn in crown_dates and dn.year >= 2026 and dn >= today:
            future_crown.append(dn)
        else:
            historical_dates.append(dn)

    frames: List[pd.DataFrame] = []

    if dry_run:
        for d in historical_dates:
            # Plausible Charlotte spring/summer/fall values without HTTP
            m = d.month
            base = 72.0 + (m - 3) * 2.5 if m <= 8 else 82.0 - (m - 8) * 3.0
            base = float(max(38.0, min(96.0, base)))
            pin = 0.02 if m in (6, 7, 8) else 0.05
            bad, hot, rain = _derive_flags(base, pin)
            frames.append(
                pd.DataFrame(
                    [
                        {
                            "date": d,
                            "temp_max_f": base,
                            "temp_min_f": base - 15.0,
                            "precipitation_inches": pin,
                            "windspeed_mph": 7.0,
                            "is_bad_weather": bad,
                            "is_hot_day": hot,
                            "is_rainy": rain,
                        }
                    ]
                )
            )
        for d in future_crown:
            frames.append(pd.DataFrame([_rows_for_crown_future(d)]))
    else:
        by_year: dict[int, List[pd.Timestamp]] = {}
        for d in historical_dates:
            by_year.setdefault(d.year, []).append(d)
        for year, dlist in sorted(by_year.items()):
            start_d = min(dlist).date()
            end_d = max(dlist).date()
            time.sleep(REQUEST_DELAY_S)
            try:
                ydf = _fetch_year_daily(year, start_d, end_d)
                if ydf.empty:
                    continue
                ydf["date"] = pd.to_datetime(ydf["date"]).dt.normalize()
                want = {pd.Timestamp(x).normalize() for x in dlist}
                ydf = ydf[ydf["date"].isin(want)]
                frames.append(ydf)
            except Exception as e:
                logger.warning("Open-Meteo fetch failed for %s: %s — using zeros for those dates", year, e)
                for d in dlist:
                    frames.append(
                        pd.DataFrame(
                            [
                                {
                                    "date": d,
                                    "temp_max_f": 0.0,
                                    "temp_min_f": 0.0,
                                    "precipitation_inches": 0.0,
                                    "windspeed_mph": 0.0,
                                    "is_bad_weather": 0,
                                    "is_hot_day": 0,
                                    "is_rainy": 0,
                                }
                            ]
                        )
                    )

    for d in future_crown:
        frames.append(pd.DataFrame([_rows_for_crown_future(d)]))

    if not frames:
        out = pd.DataFrame()
    else:
        out = pd.concat(frames, ignore_index=True)
        out["date"] = pd.to_datetime(out["date"]).dt.normalize()
        out = out.drop_duplicates(subset=["date"], keep="last").sort_values("date")

    if save:
        path = settings.DATA_PROCESSED / "game_weather.csv"
        out.to_csv(path, index=False)
        logger.info("Saved %s rows → %s", len(out), path)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    fetch_game_weather(dry_run=False)
