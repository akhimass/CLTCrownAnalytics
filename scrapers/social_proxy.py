# scrapers/social_proxy.py
"""
Proxy for social-media buzz: recency since last home game, series position, rivalry.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def _rivalry_mult(opponent: str) -> float:
    if "greensboro" in (opponent or "").lower():
        return 1.15
    return 1.0


def _recency_score(days_since_last: Optional[float]) -> float:
    if days_since_last is None:
        return 1.0
    if days_since_last <= 7:
        return 0.6
    if days_since_last <= 14:
        return 0.8
    return 1.0


def _series_mult(position: int) -> float:
    if position <= 1:
        return 1.1
    if position == 2:
        return 0.95
    return 0.90


def compute_crown_social_buzz_scores(crown_df: pd.DataFrame) -> pd.Series:
    """
    Per-row social buzz proxy for Crown home schedule (sorted by date).

    social_buzz_score = recency_score * series_position_mult * rivalry_mult
    """
    df = crown_df.sort_values("date").reset_index(drop=True)
    scores = []
    prev_date: Optional[pd.Timestamp] = None
    prev_opp: Optional[str] = None
    series_pos = 0

    for _, row in df.iterrows():
        d = pd.Timestamp(row["date"]).normalize()
        opp = str(row.get("opponent", ""))

        if prev_date is None:
            days_since = None
        else:
            days_since = float((d - prev_date).days)

        rec = _recency_score(days_since)

        same_series = (
            prev_opp is not None
            and opp.lower() == prev_opp.lower()
            and days_since is not None
            and days_since <= 7
        )
        if same_series:
            series_pos += 1
        else:
            series_pos = 1

        sm = _series_mult(series_pos)
        rm = _rivalry_mult(opp)
        scores.append(rec * sm * rm)

        prev_date = d
        prev_opp = opp

    return pd.Series(scores, index=df.index)


def attach_social_buzz(crown_df: pd.DataFrame) -> pd.DataFrame:
    """Return copy with social_buzz_score aligned to original row order."""
    out = crown_df.copy()
    order = out.sort_values("date").index
    sorted_df = out.loc[order].reset_index(drop=True)
    buzz = compute_crown_social_buzz_scores(sorted_df)
    out.loc[order, "social_buzz_score"] = buzz.values
    out["social_buzz_score"] = out["social_buzz_score"].fillna(0.8)
    return out
