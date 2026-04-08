# models/feature_engineering.py
import logging
import numpy as np
import pandas as pd

from config.constants import (
    CONCESSION_VALUE_INDEX,
    PARKING_COSTS,
    PROMO_MULTIPLIERS,
    TOTAL_COA_ADVANTAGE,
    TRANSIT_SCORE,
)
from config.settings import settings

logger = logging.getLogger(__name__)

FC_OPPONENT_TIERS = {
    "Inter Miami": 3, "Atlanta United": 2, "Atlanta United FC": 2,
    "Nashville SC": 2, "LA Galaxy": 2, "NYCFC": 2, "New York City FC": 2,
    "Columbus Crew": 1, "Philadelphia Union": 1, "DC United": 1,
    "Toronto FC": 1, "New England Revolution": 1, "San Diego FC": 1,
    "FC Cincinnati": 2, "Chicago Fire FC": 1, "MLS All-Star Game": 3,
    "default": 1,
}
CROWN_OPPONENT_TIERS = {
    "Jacksonville Waves": 1, "Savannah Steel": 1, "Greensboro Groove": 2, "default": 1,
}


def score_crown_opponent(opponent: str) -> int:
    """
    Map Crown home opponent name to model quality tier (1–3).

    Args:
        opponent: Opponent string as in the Crown schedule.

    Returns:
        Integer tier for MLR / simulator opponent_tier feature.
    """
    return int(CROWN_OPPONENT_TIERS.get(opponent, CROWN_OPPONENT_TIERS["default"]))


def _safe_series(df, col, default, n):
    return df[col] if col in df.columns else pd.Series([default] * n)


def _merge_game_weather(out: pd.DataFrame) -> pd.DataFrame:
    path = settings.DATA_PROCESSED / "game_weather.csv"
    if not path.exists():
        out = out.copy()
        out["is_bad_weather"] = 0
        return out
    w = pd.read_csv(path, parse_dates=["date"])
    w["date"] = w["date"].dt.normalize()
    out = out.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    if "is_bad_weather" in out.columns:
        out = out.drop(columns=["is_bad_weather"])
    sub = w[["date", "is_bad_weather"]].drop_duplicates("date", keep="last")
    out = out.merge(sub, on="date", how="left")
    out["is_bad_weather"] = out["is_bad_weather"].fillna(0).astype(int)
    return out


def _school_and_holiday(out: pd.DataFrame) -> pd.DataFrame:
    from pipelines.calendar_features import (
        get_school_session_score,
        is_holiday_weekend,
        is_move_in_weekend,
    )

    out = out.copy()
    out["school_session_score"] = out["date"].map(get_school_session_score)
    out["is_holiday_weekend"] = out["date"].map(is_holiday_weekend).astype(int)
    out["is_move_in_weekend"] = out["date"].map(is_move_in_weekend).astype(int)
    return out


def _competition_columns(out: pd.DataFrame) -> pd.DataFrame:
    from pipelines.event_calendar import get_competition_score, get_competing_event_name

    out = out.copy()

    def _score(d):
        return get_competition_score(pd.Timestamp(d).strftime("%Y-%m-%d"))

    def _name(d):
        return get_competing_event_name(pd.Timestamp(d).strftime("%Y-%m-%d"))

    out["competing_event_score"] = out["date"].map(_score).astype(float)
    out["competing_event_name"] = out["date"].map(_name)
    return out


def _infer_promo_multiplier(promo_name):
    if not promo_name:
        return PROMO_MULTIPLIERS["none"]
    name = str(promo_name).lower()
    if any(k in name for k in ["giveaway", "gift", "jersey", "shirt", "hat", "towel"]):
        return PROMO_MULTIPLIERS["giveaway"]
    if any(k in name for k in ["$1", "discount", "dollar", "free"]):
        return PROMO_MULTIPLIERS["discount_price"]
    if any(k in name for k in ["night", "appreciation", "tribute", "pride", "cultura"]):
        return PROMO_MULTIPLIERS["community_night"]
    if any(k in name for k in ["star", "autograph", "meet"]):
        return PROMO_MULTIPLIERS["star_feature"]
    return PROMO_MULTIPLIERS["theme_night"]


def engineer_fc_features(df):
    out = df.copy()
    n = len(out)
    if "has_promo" not in out.columns:
        out["has_promo"] = 0
    if "month" not in out.columns:
        out["month"] = out["date"].dt.month
    out["opponent_tier"] = _safe_series(out, "opponent", "default", n).map(
        lambda x: FC_OPPONENT_TIERS.get(x, FC_OPPONENT_TIERS["default"])
    )
    promo_names = _safe_series(out, "promo_name", "", n)
    out["promo_multiplier"] = promo_names.map(_infer_promo_multiplier)
    out["is_evening"] = _safe_series(out, "hour", 19, n).apply(lambda h: int(h >= 17))
    out["day_num"] = out["date"].dt.dayofweek
    if "is_weekend" not in out.columns:
        out["is_weekend"] = out["date"].dt.dayofweek.isin([4, 5, 6]).astype(int)
    out["game_number"] = out.groupby("season").cumcount() + 1 if "season" in out.columns else range(n)
    out["transit_score"] = TRANSIT_SCORE.get("fc", 2)
    att = _safe_series(out, "attendance", np.nan, n)
    out["fill_rate"] = (att / 38_000).clip(0, 1)
    out["concession_value_index"] = CONCESSION_VALUE_INDEX["fc"]
    out["has_bundle_offer"] = 0
    out["parking_avg_cost"] = float(PARKING_COSTS["fc"]["avg"])
    out["parking_vs_fc_delta"] = 0.0
    out["parking_free"] = 0
    out["total_coa_vs_fc"] = 0
    out["social_buzz_score"] = 0.8
    out = _merge_game_weather(out)
    out = _school_and_holiday(out)
    out = _competition_columns(out)
    return out.dropna(subset=["attendance"]) if "attendance" in out.columns else out


def engineer_knights_features(df):
    out = df.copy()
    n = len(out)
    if "has_promo" not in out.columns:
        out["has_promo"] = 0
    if "month" not in out.columns:
        out["month"] = out["date"].dt.month
    out["opponent_tier"] = 1
    has_promo = _safe_series(out, "has_promo", 0, n)
    out["promo_multiplier"] = has_promo.map(
        lambda x: PROMO_MULTIPLIERS["giveaway"] if x else PROMO_MULTIPLIERS["none"]
    )
    out["is_evening"] = _safe_series(out, "hour", 18, n).apply(lambda h: int(h >= 17))
    out["day_num"] = out["date"].dt.dayofweek
    if "is_weekend" not in out.columns:
        out["is_weekend"] = out["date"].dt.dayofweek.isin([4, 5, 6]).astype(int)
    out["game_number"] = out.groupby("season").cumcount() + 1 if "season" in out.columns else range(n)
    out["transit_score"] = TRANSIT_SCORE.get("knights", 2)
    att = _safe_series(out, "attendance", np.nan, n)
    out["fill_rate"] = (att / 10_200).clip(0, 1)
    out["concession_value_index"] = CONCESSION_VALUE_INDEX["knights"]
    out["has_bundle_offer"] = 0
    out["parking_avg_cost"] = float(PARKING_COSTS["knights"]["avg"])
    out["parking_vs_fc_delta"] = float(PARKING_COSTS["fc"]["avg"] - PARKING_COSTS["knights"]["avg"])
    out["parking_free"] = 0
    out["total_coa_vs_fc"] = 0
    out["social_buzz_score"] = 0.8
    out = _merge_game_weather(out)
    out = _school_and_holiday(out)
    out = _competition_columns(out)
    return out.dropna(subset=["attendance"]) if "attendance" in out.columns else out


def engineer_crown_features(df, fc_conflict=True):
    out = df.copy()
    n = len(out)
    out["opponent_tier"] = _safe_series(out, "opponent", "default", n).map(score_crown_opponent)
    if "has_promo" not in out.columns:
        out["has_promo"] = 0
    if "month" not in out.columns:
        out["month"] = out["date"].dt.month
    if "promo_name" not in out.columns:
        out["promo_name"] = ""
    out["promo_multiplier"] = out["promo_name"].map(_infer_promo_multiplier)
    out["is_evening"] = _safe_series(out, "hour", 19, n).apply(lambda h: int(h >= 17))
    out["day_num"] = out["date"].dt.dayofweek
    if "is_weekend" not in out.columns:
        out["is_weekend"] = out["date"].dt.dayofweek.isin([4, 5, 6]).astype(int)
    out["game_number"] = range(1, n + 1)
    out["transit_score"] = TRANSIT_SCORE.get("crown", 1)
    out["transit_penalty"] = out["transit_score"].map({0: -0.15, 1: -0.08, 2: 0.0}).fillna(-0.08)
    if "cannibalization_pct" not in out.columns:
        out["cannibalization_pct"] = 0.0
    out["ticket_price"] = 17.0
    out["has_group_discount"] = 0
    out["concession_value_index"] = CONCESSION_VALUE_INDEX["crown_baseline"]
    out["has_bundle_offer"] = 0
    out["parking_avg_cost"] = float(PARKING_COSTS["crown"]["avg"])
    out["parking_vs_fc_delta"] = float(PARKING_COSTS["fc"]["avg"] - PARKING_COSTS["crown"]["avg"])
    out["parking_free"] = 1
    out["total_coa_vs_fc"] = float(TOTAL_COA_ADVANTAGE["crown_vs_fc"])
    out["total_coa_vs_knights"] = float(TOTAL_COA_ADVANTAGE["crown_vs_knights"])
    if "social_buzz_score" not in out.columns:
        out["social_buzz_score"] = 0.8
    out = _merge_game_weather(out)
    out = _school_and_holiday(out)
    out = _competition_columns(out)
    return out


def build_ohe_matrix(df, cat_cols):
    return pd.get_dummies(df, columns=cat_cols, drop_first=True)
