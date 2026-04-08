# models/scenario_simulator.py
"""
Single-game what-if simulator: attendance + revenue for one Crown home game.

Uses trained Ridge/OLS MLR from data/processed/mlr_model.pkl when present;
otherwise falls back to constants-based fill-rate math.

Run standalone:
    python -m models.scenario_simulator --promo giveaway --price 14 --shuttle --opponent "Greensboro Groove"
"""
from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import settings
from config.constants import (
    VENUES,
    PROMO_MULTIPLIERS,
    crown_conflict_fill_multiplier,
    BASELINE_FILL_RATE,
    BASELINE_ANCILLARY,
    STRATEGY_ANCILLARY,
    SIMULATOR_ATTENDANCE_CI_FANS,
    TRANSIT_SCORE,
    SHUTTLE_FILL_RATE_LIFT,
    CONCESSION_VALUE_INDEX,
    PARKING_COSTS,
    TOTAL_COA_ADVANTAGE,
    COA_CONCESSION_AVG_PER_PERSON,
    COA_TICKET_ASSUMPTIONS,
)
from models.feature_engineering import score_crown_opponent
from pipelines.event_calendar import competition_score_for_event_name_fragment

logger = logging.getLogger(__name__)

CAPACITY = VENUES["crown"]["capacity"]

PROMO_TYPE_MAP: Dict[str, Tuple[str, int]] = {
    "none": ("none", 0),
    "theme": ("theme_night", 1),
    "giveaway": ("giveaway", 1),
    "discount": ("discount_price", 1),
    "star": ("star_feature", 1),
    "community": ("community_night", 1),
}


@dataclass
class ScenarioOutcome:
    """Point estimates for one simulated Crown home game."""

    projected_attendance: int
    fill_rate_pct: float
    ticket_revenue: float
    ancillary_revenue: float
    total_revenue: float
    confidence_interval: Tuple[int, int]
    model_source: str
    total_coa_per_person: float
    value_vs_fc: float
    value_vs_knights: float


def _normalize_weekend(day_of_week: str) -> int:
    """Return 1 if Fri/Sat/Sun."""
    d = (day_of_week or "").strip().lower()
    if d in ("friday", "saturday", "sunday"):
        return 1
    if len(d) >= 3 and d[:3] in ("fri", "sat", "sun"):
        return 1
    return 0


def _resolve_promo(promo_type: str) -> Tuple[str, int, float]:
    """Map CLI promo label to (PROMO_MULTIPLIERS key, has_promo flag, multiplier value)."""
    p = (promo_type or "none").strip().lower()
    key, has_promo = PROMO_TYPE_MAP.get(p, ("none", 0))
    mult = float(PROMO_MULTIPLIERS.get(key, 1.0))
    return key, has_promo, mult


def _load_mlr():
    """Load pickled AttendanceMLR if available."""
    path = settings.DATA_PROCESSED / "mlr_model.pkl"
    if not path.exists():
        return None
    try:
        from models.attendance_mlr import AttendanceMLR

        return AttendanceMLR.load(path)
    except Exception as exc:
        logger.warning("MLR pickle load failed (%s); using constants fallback", exc)
        return None


def _fallback_normalized_fill(
    promo_mult: float,
    opponent: str,
    is_weekend: int,
    is_evening: int,
    transit_score: int,
    game_number: int,
    month: int,
) -> float:
    """Heuristic fill rate when no trained model is available (conflicts applied later)."""
    tier = score_crown_opponent(opponent)
    fill = BASELINE_FILL_RATE * promo_mult
    fill *= 1.0 + 0.04 * (tier - 1)
    fill *= 1.0 + 0.03 * is_weekend
    fill *= 1.0 + 0.02 * is_evening
    fill *= 1.0 + 0.02 * max(0, transit_score - 1)
    fill *= 1.0 - 0.001 * abs(game_number - 9)
    fill *= 1.0 + 0.01 * (month - 6)
    return float(np.clip(fill, 0.0, 1.0))


def _confidence_half_width(mlr, base_norm: float) -> int:
    """Half-width (fans) for approximate 95% interval."""
    half = SIMULATOR_ATTENDANCE_CI_FANS
    if mlr is not None and getattr(mlr, "ols_result", None) is not None:
        try:
            mse = float(mlr.ols_result.mse_resid)
            se_norm = float(np.sqrt(mse))
            half = int(np.clip(se_norm * 1.96 * CAPACITY, 120.0, 450.0))
        except Exception:
            pass
    return half


def _resolve_competing_multiplier(competing_event: str, competing_event_score: float) -> float:
    ces = float(competing_event_score)
    frag = competition_score_for_event_name_fragment(competing_event or "")
    if frag is not None:
        ces = min(ces, frag)
    return ces


def simulate_scenario(
    promo_type: str = "none",
    ticket_price: float = 17.0,
    has_shuttle: bool = False,
    opponent: str = "Jacksonville Waves",
    day_of_week: str = "Saturday",
    hour: int = 19,
    fc_conflict: bool = False,
    knights_conflict: bool = False,
    game_number: int = 9,
    month: Optional[int] = None,
    mlr=None,
    prefer_mlr: bool = True,
    is_bad_weather: bool = False,
    has_bundle_offer: bool = False,
    school_session_score: float = 0.4,
    is_holiday_weekend: bool = False,
    competing_event_score: float = 1.0,
    competing_event: str = "",
    social_buzz_score: float = 0.8,
    concession_value_index: float = 0.55,
    parking_cost: float = 0.0,
) -> ScenarioOutcome:
    """
    Project attendance and revenue for one Crown home game.

    Crown parking at Bojangles is **free** — default ``parking_cost=0``.
    ``concession_value_index``: lower = better fan value (see ``CONCESSION_VALUE_INDEX``).
    """
    _, has_promo, promo_mult = _resolve_promo(promo_type)
    is_weekend = _normalize_weekend(day_of_week)
    is_evening = int(hour >= 17)
    mo = int(month if month is not None else 6)
    transit_score = TRANSIT_SCORE["crown"]

    cvi = float(concession_value_index)
    if has_bundle_offer:
        cvi = float(CONCESSION_VALUE_INDEX["crown_strategy"])

    ces = _resolve_competing_multiplier(competing_event, competing_event_score)

    if mlr is not None:
        mlr_model = mlr
    elif prefer_mlr:
        mlr_model = _load_mlr()
    else:
        mlr_model = None

    row = pd.DataFrame(
        [
            {
                "has_promo": has_promo,
                "promo_multiplier": promo_mult,
                "opponent_tier": int(score_crown_opponent(opponent)),
                "is_weekend": is_weekend,
                "is_evening": is_evening,
                "game_number": int(game_number),
                "transit_score": transit_score,
                "month": mo,
                "is_bad_weather": int(is_bad_weather),
                "concession_value_index": cvi,
                "has_bundle_offer": int(has_bundle_offer),
                "school_session_score": float(school_session_score),
                "is_holiday_weekend": int(is_holiday_weekend),
                "competing_event_score": float(ces),
                "social_buzz_score": float(social_buzz_score),
                "parking_avg_cost": float(parking_cost),
                "parking_free": int(PARKING_COSTS["crown"]["free"] and parking_cost <= 0),
                "total_coa_vs_fc": float(TOTAL_COA_ADVANTAGE["crown_vs_fc"]),
            }
        ]
    )

    model_source = "constants_fallback"
    if mlr_model is not None and getattr(mlr_model, "trained", False):
        norm = float(mlr_model.predict(row)[0])
        model_source = "mlr_pickle"
    else:
        norm = _fallback_normalized_fill(
            promo_mult,
            opponent,
            is_weekend,
            is_evening,
            transit_score,
            game_number,
            mo,
        )
        norm *= float(ces)
        if is_bad_weather:
            norm *= 0.94
        norm *= 1.0 + 0.06 * (float(social_buzz_score) - 0.8)
        # Lower concession index = better value → lift attendance slightly
        norm *= 1.0 + 0.10 * (float(CONCESSION_VALUE_INDEX["crown_baseline"]) - cvi)
        norm *= 1.0 + 0.02 * float(school_session_score)
        if is_holiday_weekend:
            norm *= 1.03

    norm *= crown_conflict_fill_multiplier(fc_conflict, knights_conflict)
    if has_shuttle:
        norm = min(1.0, norm + SHUTTLE_FILL_RATE_LIFT)
    norm = float(np.clip(norm, 0.0, 1.0))

    attendance = int(round(norm * CAPACITY))
    attendance = int(np.clip(attendance, 0, CAPACITY))
    fill_pct = round(100.0 * attendance / CAPACITY, 2)

    half = _confidence_half_width(mlr_model if model_source == "mlr_pickle" else None, norm)
    lo = int(np.clip(attendance - half, 0, CAPACITY))
    hi = int(np.clip(attendance + half, 0, CAPACITY))

    ancillary_rate = STRATEGY_ANCILLARY if (has_promo or has_shuttle) else BASELINE_ANCILLARY
    ticket_revenue = float(attendance * ticket_price)
    ancillary_revenue = float(attendance * ancillary_rate)
    total_revenue = ticket_revenue + ancillary_revenue

    crown_conc = float(COA_CONCESSION_AVG_PER_PERSON["crown"])
    total_coa = float(ticket_price) + float(parking_cost) + crown_conc
    fc_coa = (
        float(COA_TICKET_ASSUMPTIONS["fc"])
        + float(PARKING_COSTS["fc"]["avg"])
        + float(COA_CONCESSION_AVG_PER_PERSON["fc"])
    )
    kn_coa = (
        float(COA_TICKET_ASSUMPTIONS["knights"])
        + float(PARKING_COSTS["knights"]["avg"])
        + float(COA_CONCESSION_AVG_PER_PERSON["knights"])
    )
    value_vs_fc = fc_coa - total_coa
    value_vs_knights = kn_coa - total_coa

    return ScenarioOutcome(
        projected_attendance=attendance,
        fill_rate_pct=fill_pct,
        ticket_revenue=ticket_revenue,
        ancillary_revenue=ancillary_revenue,
        total_revenue=total_revenue,
        confidence_interval=(lo, hi),
        model_source=model_source,
        total_coa_per_person=round(total_coa, 2),
        value_vs_fc=round(value_vs_fc, 2),
        value_vs_knights=round(value_vs_knights, 2),
    )


def simulate_scenario_dict(**kwargs: Any) -> Dict[str, Any]:
    """Same as simulate_scenario but returns a plain dict (for reporting/JSON)."""
    out = simulate_scenario(**kwargs)
    return {
        "projected_attendance": out.projected_attendance,
        "fill_rate_pct": out.fill_rate_pct,
        "ticket_revenue": out.ticket_revenue,
        "ancillary_revenue": out.ancillary_revenue,
        "total_revenue": out.total_revenue,
        "confidence_interval": list(out.confidence_interval),
        "model_source": out.model_source,
        "total_coa_per_person": out.total_coa_per_person,
        "value_vs_fc": out.value_vs_fc,
        "value_vs_knights": out.value_vs_knights,
    }


def _format_outcome(o: ScenarioOutcome) -> str:
    lo, hi = o.confidence_interval
    return (
        f"projected_attendance={o.projected_attendance}  "
        f"fill_rate_pct={o.fill_rate_pct}  "
        f"ticket_revenue=${o.ticket_revenue:,.0f}  "
        f"ancillary_revenue=${o.ancillary_revenue:,.0f}  "
        f"total_revenue=${o.total_revenue:,.0f}  "
        f"ci_fans=[{lo}, {hi}]  source={o.model_source}  "
        f"coa_pp=${o.total_coa_per_person:.0f}  "
        f"value_vs_fc=${o.value_vs_fc:.0f}  value_vs_knights=${o.value_vs_knights:.0f}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Crown single-game scenario simulator")
    ap.add_argument("--promo", default="none", help="none|theme|giveaway|discount|star|community")
    ap.add_argument("--price", type=float, default=17.0, help="Average ticket price ($)")
    ap.add_argument("--shuttle", action="store_true", help="Blue Line shuttle on")
    ap.add_argument("--opponent", default="Greensboro Groove")
    ap.add_argument("--weekday", default="Saturday", help="Day of week label")
    ap.add_argument("--hour", type=int, default=19)
    ap.add_argument("--fc-conflict", action="store_true")
    ap.add_argument("--knights-conflict", action="store_true")
    ap.add_argument("--game-number", type=int, default=9)
    ap.add_argument("--month", type=int, default=None)
    ap.add_argument("--weather-bad", action="store_true", help="Bad weather (rain / extremes)")
    ap.add_argument("--bundle", action="store_true", help="Strategy concession bundle / value pricing")
    ap.add_argument("--holiday", action="store_true", help="Holiday weekend window")
    ap.add_argument("--parking-cost", type=float, default=0.0, help="Parking $ (Crown default 0)")
    ap.add_argument(
        "--competing",
        type=str,
        default="",
        help='Competing event name fragment (e.g. "Post Malone Concert")',
    )
    args = ap.parse_args()

    res = simulate_scenario(
        promo_type=args.promo,
        ticket_price=args.price,
        has_shuttle=args.shuttle,
        opponent=args.opponent,
        day_of_week=args.weekday,
        hour=args.hour,
        fc_conflict=args.fc_conflict,
        knights_conflict=args.knights_conflict,
        game_number=args.game_number,
        month=args.month,
        is_bad_weather=args.weather_bad,
        has_bundle_offer=args.bundle,
        is_holiday_weekend=args.holiday,
        parking_cost=args.parking_cost,
        competing_event=args.competing,
    )
    print(_format_outcome(res))
