# pipelines/build_master_calendar.py
"""
Merges FC, Knights, Checkers game logs into a single master calendar.
Computes conflict flags, cannibalization variables, and saves to processed/.

Run standalone:
    python -m pipelines.build_master_calendar
"""
import logging
from pathlib import Path

import pandas as pd
import numpy as np

from config.settings import settings
from config.constants import (
    CROWN_CONFLICT_PENALTY_CAP,
    CROWN_CONFLICT_PENALTIES,
    CROWN_SAME_TIME_THRESHOLD_HOURS,
    TRANSIT_SCORE,
    TRANSIT_MINUTES,
)
from scrapers.social_proxy import attach_social_buzz
from pipelines.event_calendar import get_competition_score, get_competing_event_name

logger = logging.getLogger(__name__)

# ── Crown 2026 full schedule (club release) ───────────────────────────────────
# Convention: "Opponent vs. Charlotte Crown" = Crown hosts in Charlotte; "Charlotte Crown at …" = road.
# is_home flags Charlotte (Bojangles) home — used for FC/Knights cannibalization + revenue; road games listed for calendar/weather.
CROWN_FULL_SCHEDULE_2026 = [
    {"date": "2026-05-15", "opponent": "Jacksonville Waves", "hour": 19, "is_home": False},
    {"date": "2026-05-21", "opponent": "Jacksonville Waves", "hour": 19, "is_home": True},
    {"date": "2026-05-25", "opponent": "Greensboro Groove", "hour": 19, "is_home": True},
    {"date": "2026-05-28", "opponent": "Savannah Steel", "hour": 19, "is_home": False},
    {"date": "2026-05-29", "opponent": "Savannah Steel", "hour": 19, "is_home": False},
    {"date": "2026-05-30", "opponent": "Savannah Steel", "hour": 19, "is_home": True},
    {"date": "2026-06-03", "opponent": "Jacksonville Waves", "hour": 12, "is_home": True},
    {"date": "2026-06-06", "opponent": "Savannah Steel", "hour": 16, "is_home": True},
    {"date": "2026-06-14", "opponent": "Savannah Steel", "hour": 14, "is_home": True},
    {"date": "2026-06-17", "opponent": "Greensboro Groove", "hour": 19, "is_home": True},
    {"date": "2026-06-18", "opponent": "Greensboro Groove", "hour": 12, "is_home": False},
    {"date": "2026-06-20", "opponent": "Greensboro Groove", "hour": 16, "is_home": False},
    {"date": "2026-06-21", "opponent": "Savannah Steel", "hour": 15, "is_home": False},
    {"date": "2026-06-26", "opponent": "Jacksonville Waves", "hour": 15, "is_home": False},
    {"date": "2026-06-27", "opponent": "Jacksonville Waves", "hour": 16, "is_home": False},
    {"date": "2026-07-03", "opponent": "Jacksonville Waves", "hour": 19, "is_home": False},
    {"date": "2026-07-05", "opponent": "Jacksonville Waves", "hour": 14, "is_home": False},
    {"date": "2026-07-10", "opponent": "Greensboro Groove", "hour": 19, "is_home": False},
    {"date": "2026-07-11", "opponent": "Greensboro Groove", "hour": 16, "is_home": False},
    {"date": "2026-07-16", "opponent": "Greensboro Groove", "hour": 12, "is_home": False},
    {"date": "2026-07-17", "opponent": "Greensboro Groove", "hour": 19, "is_home": False},
    {"date": "2026-07-19", "opponent": "Greensboro Groove", "hour": 14, "is_home": False},
    {"date": "2026-07-23", "opponent": "Savannah Steel", "hour": 19, "is_home": False},
    {"date": "2026-07-30", "opponent": "Greensboro Groove", "hour": 19, "is_home": True},
    {"date": "2026-08-01", "opponent": "Savannah Steel", "hour": 16, "is_home": True},
    {"date": "2026-08-02", "opponent": "Jacksonville Waves", "hour": 14, "is_home": True},
    {"date": "2026-08-05", "opponent": "Greensboro Groove", "hour": 19, "is_home": True},
    {"date": "2026-08-08", "opponent": "Savannah Steel", "hour": 16, "is_home": True},
    {"date": "2026-08-09", "opponent": "Savannah Steel", "hour": 14, "is_home": True},
    {"date": "2026-08-13", "opponent": "Jacksonville Waves", "hour": 19, "is_home": True},
    {"date": "2026-08-15", "opponent": "Jacksonville Waves", "hour": 16, "is_home": True},
    {"date": "2026-08-21", "opponent": "Savannah Steel", "hour": 19, "is_home": False},
    {"date": "2026-08-22", "opponent": "Greensboro Groove", "hour": 16, "is_home": True},
    {"date": "2026-08-23", "opponent": "Greensboro Groove", "hour": 14, "is_home": True},
]

# Charlotte home only — FC/Knights conflict + revenue models use this list.
CROWN_HOME_GAMES = [
    {"date": g["date"], "opponent": g["opponent"], "hour": g["hour"]}
    for g in CROWN_FULL_SCHEDULE_2026
    if g["is_home"]
]

assert len(CROWN_FULL_SCHEDULE_2026) == 34
assert len(CROWN_HOME_GAMES) == 17

# Charlotte FC 2026 home — verified club schedule (used for Crown same-day conflict + time-aware penalties).
# hour 19.5 = 7:30 PM; May 13 7:00 PM → 19; Jul 22 8:00 PM → 20; Leagues Cup evenings → 19.5.
FC_2026_HOME = [
    {"date": "2026-03-07", "opponent": "Austin FC", "hour": 19.5},
    {"date": "2026-03-14", "opponent": "Inter Miami", "hour": 19.5},
    {"date": "2026-03-21", "opponent": "New York Red Bulls", "hour": 19.5},
    {"date": "2026-04-04", "opponent": "Philadelphia Union", "hour": 19.5},
    {"date": "2026-04-11", "opponent": "Nashville SC", "hour": 19.5},
    {"date": "2026-05-09", "opponent": "FC Cincinnati", "hour": 19.5},
    {"date": "2026-05-13", "opponent": "New York City FC", "hour": 19},
    {"date": "2026-05-16", "opponent": "Toronto FC", "hour": 19.5},
    {"date": "2026-05-23", "opponent": "New England Revolution", "hour": 19.5},
    {"date": "2026-07-22", "opponent": "Atlanta United", "hour": 20},
    {"date": "2026-08-04", "opponent": "Pumas (Leagues Cup)", "hour": 19.5},
    {"date": "2026-08-07", "opponent": "Atletico San Luis (Leagues Cup)", "hour": 19.5},
    {"date": "2026-08-11", "opponent": "Pacific FC (Leagues Cup)", "hour": 19.5},
    {"date": "2026-08-15", "opponent": "Columbus Crew", "hour": 19.5},
    {"date": "2026-08-22", "opponent": "DC United", "hour": 19.5},
    {"date": "2026-09-05", "opponent": "Houston Dynamo", "hour": 19.5},
    {"date": "2026-09-26", "opponent": "Chicago Fire", "hour": 19.5},
    {"date": "2026-10-10", "opponent": "FC Dallas", "hour": 19.5},
    {"date": "2026-10-28", "opponent": "CF Montreal", "hour": 19.5},
    {"date": "2026-10-31", "opponent": "Orlando City", "hour": 19.5},
]

def load_team_data(team: str) -> pd.DataFrame:
    path = settings.DATA_PROCESSED / f"{team}_games.csv"
    if path.exists():
        df = pd.read_csv(path, parse_dates=["date"])
        logger.info(f"Loaded {len(df)} rows for {team}")
        return df
    logger.warning(f"No processed data for {team} at {path}")
    return pd.DataFrame()


def build_crown_schedule() -> pd.DataFrame:
    df = pd.DataFrame(CROWN_HOME_GAMES)
    df["date"] = pd.to_datetime(df["date"])
    df["team"] = "charlotte_crown"
    df["season"] = 2026
    df["day_of_week"] = df["date"].dt.day_name()
    df["is_weekend"] = df["date"].dt.dayofweek.isin([4, 5, 6]).astype(int)
    df["month"] = df["date"].dt.month
    df["transit_score"] = TRANSIT_SCORE["crown"]
    df["transit_minutes"] = TRANSIT_MINUTES["crown"]
    return df


def build_fc_2026() -> pd.DataFrame:
    df = pd.DataFrame(FC_2026_HOME)
    df["date"] = pd.to_datetime(df["date"])
    df["team"] = "charlotte_fc"
    df["season"] = 2026
    return df


def _fc_opponent_is_leagues_cup(opponent: str) -> bool:
    o = opponent.lower()
    if "leagues cup" in o:
        return True
    return any(k in o for k in ("pumas", "atletico san luis", "pacific fc", "pacific "))


def compute_time_aware_cannibal_penalty(
    crown_row: pd.Series,
    fc_df: pd.DataFrame,
    knights_df: pd.DataFrame,
) -> float:
    """
    Sum time-bucket penalties for same-calendar-day FC and/or Knights home vs Crown home.
    Same-time uses gap < CROWN_SAME_TIME_THRESHOLD_HOURS (strict — gap == 2h → staggered).
    """
    d = pd.Timestamp(crown_row["date"]).normalize()
    crown_h = float(crown_row.get("hour", 19))
    penalty = 0.0

    fc_on = fc_df[fc_df["date"].dt.normalize() == d]
    if not fc_on.empty:
        fc_h = float(fc_on["hour"].iloc[0]) if "hour" in fc_on.columns else 19.0
        gap = abs(crown_h - fc_h)
        opp = str(fc_on["opponent"].iloc[0])
        if _fc_opponent_is_leagues_cup(opp):
            penalty += CROWN_CONFLICT_PENALTIES["leagues_cup_adjacent"]
        elif gap < CROWN_SAME_TIME_THRESHOLD_HOURS:
            penalty += CROWN_CONFLICT_PENALTIES["fc_same_time"]
        else:
            penalty += CROWN_CONFLICT_PENALTIES["fc_same_evening"]

    if not knights_df.empty:
        kn_on = knights_df[knights_df["date"].dt.normalize() == d]
        if not kn_on.empty:
            k_h = float(kn_on["hour"].iloc[0]) if "hour" in kn_on.columns else 19.0
            gap_k = abs(crown_h - k_h)
            if gap_k < CROWN_SAME_TIME_THRESHOLD_HOURS:
                penalty += CROWN_CONFLICT_PENALTIES["knights_same_time"]
            else:
                penalty += CROWN_CONFLICT_PENALTIES["knights_staggered"]

    return float(min(penalty, CROWN_CONFLICT_PENALTY_CAP))


def add_conflict_flags(crown: pd.DataFrame,
                       fc: pd.DataFrame,
                       knights: pd.DataFrame) -> pd.DataFrame:
    """
    For each Crown home game, flag same-day conflicts with FC and Knights.
    cannibalization_pct = time-aware fractional penalty (see CROWN_CONFLICT_PENALTIES).
    """
    fc = fc.copy() if not fc.empty else fc
    kn = knights.copy() if not knights.empty else knights
    if not fc.empty and "hour" not in fc.columns:
        fc["hour"] = 19
    if not kn.empty and "hour" not in kn.columns:
        kn["hour"] = 19

    fc_dates = set(fc["date"].dt.normalize())
    kn_dates = set(kn["date"].dt.normalize()) if not kn.empty else set()

    crown = crown.copy()
    crown["fc_same_day"] = crown["date"].dt.normalize().isin(fc_dates).astype(int)
    crown["knights_same_day"] = crown["date"].dt.normalize().isin(kn_dates).astype(int)
    crown["conflict_score"] = crown["fc_same_day"] + crown["knights_same_day"]

    penalties = [
        compute_time_aware_cannibal_penalty(row, fc, kn)
        for _, row in crown.iterrows()
    ]
    crown["cannibalization_pct"] = penalties
    crown["cannibalization_pct_time_adjusted"] = crown["cannibalization_pct"]

    def risk_label(row):
        if row["fc_same_day"] and row["conflict_score"] >= 1:
            return "HIGH"
        if row["conflict_score"] == 1:
            return "MODERATE"
        if row["conflict_score"] == 0:
            return "LOW"
        return "LOW"

    crown["conflict_risk"] = crown.apply(risk_label, axis=1)
    return crown


def get_crown_home_conflict_lookup() -> dict[str, tuple[int, int]]:
    """
    Single source of same-night flags for Crown home games.
    Keys: 'YYYY-MM-DD'; values: (fc_same_day, knights_same_day) as 0/1.
    """
    m = build_master(save=False)
    out: dict[str, tuple[int, int]] = {}
    for _, row in m.iterrows():
        ds = pd.Timestamp(row["date"]).strftime("%Y-%m-%d")
        out[ds] = (int(row["fc_same_day"]), int(row["knights_same_day"]))
    return out


def get_crown_home_penalty_lookup() -> dict[str, float]:
    """Canonical time-aware penalty fraction per Crown home date (matches cannibalization_pct)."""
    m = build_master(save=False)
    return {
        pd.Timestamp(r["date"]).strftime("%Y-%m-%d"): float(r["cannibalization_pct"])
        for _, r in m.iterrows()
    }


def build_master(save: bool = True) -> pd.DataFrame:
    fc_hist = load_team_data("fc")
    knights_hist = load_team_data("knights")

    crown = build_crown_schedule()
    fc_2026 = build_fc_2026()

    # Combine FC historical + 2026 forward-looking (avoid dupes if 2026 already in processed CSV)
    fc_2026["date"] = pd.to_datetime(fc_2026["date"])
    if not fc_hist.empty:
        fc_hist = fc_hist.copy()
        fc_hist["date"] = pd.to_datetime(fc_hist["date"])
        if "hour" not in fc_hist.columns:
            fc_hist["hour"] = 19
        have = set(fc_hist["date"].dt.normalize())
        fc_extra = fc_2026[~fc_2026["date"].dt.normalize().isin(have)]
        fc_all = pd.concat([fc_hist, fc_extra], ignore_index=True)
    else:
        fc_all = fc_2026
    fc_all["date"] = pd.to_datetime(fc_all["date"])

    if not knights_hist.empty:
        knights_hist["date"] = pd.to_datetime(knights_hist["date"])

    # Add conflict flags to Crown schedule
    crown = add_conflict_flags(crown, fc_all, knights_hist)
    crown = attach_social_buzz(crown)
    crown["competing_event_score"] = crown["date"].map(
        lambda d: get_competition_score(pd.Timestamp(d).strftime("%Y-%m-%d"))
    )
    crown["competing_event_name"] = crown["date"].map(
        lambda d: get_competing_event_name(pd.Timestamp(d).strftime("%Y-%m-%d"))
    )

    # Cross-reference: create a date-indexed lookup of what else is happening
    all_games = []
    for _, row in crown.iterrows():
        d = row["date"].normalize()
        fc_on_day = fc_all[fc_all["date"].dt.normalize() == d]
        knights_on_day = knights_hist[knights_hist["date"].dt.normalize() == d] if not knights_hist.empty else pd.DataFrame()

        fc_h = np.nan
        if not fc_on_day.empty and "hour" in fc_on_day.columns:
            fc_h = float(fc_on_day["hour"].iloc[0])
        kn_h = np.nan
        if not knights_on_day.empty and "hour" in knights_on_day.columns:
            kn_h = float(knights_on_day["hour"].iloc[0])

        all_games.append({
            **row.to_dict(),
            "fc_opponent": fc_on_day["opponent"].iloc[0] if not fc_on_day.empty else "",
            "fc_attendance_est": fc_on_day["attendance"].iloc[0] if ("attendance" in fc_on_day.columns and not fc_on_day.empty) else None,
            "fc_conflict_hour": fc_h,
            "knights_opponent": knights_on_day["opponent"].iloc[0] if not knights_on_day.empty else "",
            "knights_attendance_est": knights_on_day["attendance"].iloc[0] if ("attendance" in knights_on_day.columns and not knights_on_day.empty) else None,
            "knights_conflict_hour": kn_h,
        })

    master = pd.DataFrame(all_games)

    if save:
        out = settings.DATA_PROCESSED / "master_calendar.csv"
        master.to_csv(out, index=False)
        logger.info(f"Saved master calendar → {out}")

    return master


def _fmt_hour_ampm(h: float | int) -> str:
    return _fmt_clock(float(h))


def _fmt_clock(h: float) -> str:
    """Local wall time from fractional hour (e.g. 19.0667 → 7:04 PM)."""
    h = float(h) % 24.0
    total_min = int(round(h * 60))
    hh24, mm = divmod(total_min, 60)
    h12 = hh24 % 12
    if h12 == 0:
        h12 = 12
    ampm = "AM" if hh24 < 12 else "PM"
    if mm == 0:
        return f"{h12}:00 {ampm}"
    return f"{h12}:{mm:02d} {ampm}"


def _print_corrected_conflict_table(master: pd.DataFrame) -> None:
    """Reference summary for Crown 2026 home (time-aware penalties)."""
    print("\nCORRECTED CROWN CONFLICT TABLE")
    print("================================")
    hdr = "Date        | Crown Game          | Crown Time | FC Same Day | Knights Same Day | Penalty | Type"
    print(hdr)
    print("-" * len(hdr))
    kn_same_time_dates: list[str] = []
    kn_staggered_dates: list[str] = []
    fc_evening_dates: list[str] = []
    both_dates: list[str] = []

    for _, r in master.sort_values("date").iterrows():
        ds = pd.Timestamp(r["date"]).strftime("%Y-%m-%d")
        mo = pd.Timestamp(r["date"]).strftime("%b %d").replace(" 0", " ")
        opp = str(r["opponent"])[:18].ljust(18)
        ct = _fmt_clock(float(r.get("hour", 19)))
        fc_on = int(r["fc_same_day"])
        kn_on = int(r["knights_same_day"])
        pct_f = float(r["cannibalization_pct"])
        pct_i = int(round(pct_f * 100))
        pen = f"{pct_i}%"

        fc_h = r.get("fc_conflict_hour", np.nan)
        kn_h = r.get("knights_conflict_hour", np.nan)

        if fc_on:
            if pd.notna(fc_h):
                fcs = _fmt_clock(float(fc_h))
                for suf in (" PM", " AM"):
                    if fcs.endswith(suf):
                        fcs = fcs[: -len(suf)]
                        break
                fc = f"Yes ({fcs})"
            else:
                fc = "Yes (7:30)"
        else:
            fc = "No"
        if kn_on:
            kn = f"Yes ({_fmt_clock(float(kn_h))})" if pd.notna(kn_h) else "Yes (7:00 PM)"
        else:
            kn = "No"

        if pct_f == 0:
            ctype = "Clean"
        elif fc_on and kn_on:
            ctype = "FC+Knights"
            both_dates.append(ds)
        elif fc_on:
            ctype = "FC evening"
            fc_evening_dates.append(ds)
        elif kn_on and pct_f >= 0.085:
            ctype = "Same-time"
            kn_same_time_dates.append(ds)
        elif kn_on:
            ctype = "Staggered"
            kn_staggered_dates.append(ds)
        else:
            ctype = "Clean"

        print(f"{mo:11} | {opp} | {ct:10} | {fc:11} | {kn:16} | {pen:7} | {ctype}")

    n = len(master)
    clean = int((master["cannibalization_pct"] == 0).sum())
    avg = float(master["cannibalization_pct"].mean() * 100)
    mx = float(master["cannibalization_pct"].max() * 100)

    def _fmt_dates(dates: list[str]) -> str:
        if not dates:
            return ""
        parts: list[str] = []
        for d in dates:
            ts = pd.Timestamp(d)
            parts.append(f"{ts.strftime('%b')} {ts.day}")
        if len(parts) == 1:
            return f" ({parts[0]})"
        return " (" + ", ".join(parts) + ")"

    print("\nTotals:")
    print(f"  Clean games (0% penalty):         {clean} of {n}")
    print(f"  Knights same-time conflicts:       {len(kn_same_time_dates)}{_fmt_dates(kn_same_time_dates)}")
    print(f"  Knights staggered same-day:        {len(kn_staggered_dates)}{_fmt_dates(kn_staggered_dates)}")
    print(f"  FC same-evening conflicts:         {len(fc_evening_dates)}{_fmt_dates(fc_evening_dates)}")
    print(f"  Games with FC + Knights both:      {len(both_dates)}")
    print(f"  Max single-game penalty:           {mx:.0f}%")
    print(f"  Avg penalty across all {n} games:   ~{avg:.1f}%")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = build_master()
    print(df[["date", "opponent", "hour", "conflict_risk", "fc_same_day", "knights_same_day",
              "cannibalization_pct", "cannibalization_pct_time_adjusted"]].to_string())
    _print_corrected_conflict_table(df)
