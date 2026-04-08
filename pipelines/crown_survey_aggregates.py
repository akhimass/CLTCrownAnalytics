# pipelines/crown_survey_aggregates.py
"""
Load Google Form export for Charlotte Crown / Checkers exploratory survey and
aggregate for presentation chart P12.

Replace data/raw/crown_survey_responses.csv with a fresh export (same column
semantics) and re-run: python -m viz.presentation_charts  # regenerates P12
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import BASE_DIR, settings

# Preferred location (see also settings.SURVEY_RESPONSES_CSV)
CROWN_SURVEY_CSV = settings.SURVEY_RESPONSES_CSV


def resolve_crown_survey_csv() -> Path | None:
    """Prefer ``data/raw/crown_survey_responses.csv``; fall back to repo root copy."""
    for p in (settings.SURVEY_RESPONSES_CSV, BASE_DIR / "crown_survey_responses.csv"):
        if p.exists():
            return p
    return None


def _strip_name(s: pd.Series) -> pd.Series:
    out = s.copy()
    out.name = None
    return out


def _find_col(df: pd.DataFrame, *needles: str) -> str | None:
    """First column whose name contains all substrings (case-insensitive)."""
    for c in df.columns:
        cl = str(c).lower()
        if all(n.lower() in cl for n in needles):
            return c
    return None


def load_crown_survey_csv(path: Path | None = None) -> pd.DataFrame:
    p = path or resolve_crown_survey_csv()
    if p is None or not p.exists():
        raise FileNotFoundError(
            "No survey CSV found. Add data/raw/crown_survey_responses.csv "
            "or crown_survey_responses.csv at the repo root (Google Form export)."
        )
    df = pd.read_csv(p, dtype=str, encoding="utf-8-sig", on_bad_lines="skip")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def shorten_factor_label(s: str, max_len: int = 36) -> str:
    s = str(s).strip()
    if "Other Social Factors" in s:
        return "Social / word-of-mouth / hype"
    if "Game (or Team) Quality" in s:
        return "Game or team quality"
    if s == "Price":
        return "Price / value"
    if s == "Promotional Nights":
        return "Promotional nights"
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def shorten_promo_label(s: str, max_len: int = 40) -> str:
    s = str(s).strip()
    if not s:
        return "(no answer)"
    if "Themed Giveaways" in s:
        return "Themed giveaways"
    if "Thirsty Thursday" in s:
        return "Thirsty Thursday / drink specials"
    if "Halftime/Pre-game" in s or "Halftime" in s:
        return "Halftime / pre-game entertainment"
    if "Both 1 and 2" in s:
        return "Both themed + drink specials"
    if "Fan contests" in s:
        return "Fan contests"
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def shorten_hear_label(s: str) -> str:
    s = str(s).strip()
    if "Social Media" in s:
        return "Online — social media"
    if "Website" in s:
        return "Online — website"
    if "Family/Friend" in s or "reccomendation" in s.lower():
        return "Family / friend"
    if "Bilboards" in s or "Flyers" in s:
        return "Billboards / flyers"
    return s if len(s) < 42 else s[:40] + "…"


def pct_series(s: pd.Series, top_n: int = 12) -> pd.Series:
    s = s.replace("", np.nan).dropna()
    if s.empty:
        return pd.Series(dtype=float)
    vc = s.value_counts(normalize=True).mul(100.0).round(1)
    return vc.head(top_n)


def aggregates_for_p12(df: pd.DataFrame) -> dict:
    """Build structured counts for P12 matplotlib layout."""
    col_factor = _find_col(df, "most important", "factor")
    col_hear = _find_col(df, "hear about")
    col_price = _find_col(df, "price", "willing")
    col_promo = _find_col(df, "promotions", "events")
    col_age = _find_col(df, "age")
    col_team = _find_col(df, "sports team", "transportation")
    col_star = _find_col(df, "notable players")

    n = len(df)

    factor_pct = pd.Series(dtype=float)
    if col_factor:
        raw = df[col_factor].astype(str).str.strip()
        factor_pct = _strip_name(
            raw.replace("", np.nan)
            .dropna()
            .map(shorten_factor_label)
            .value_counts(normalize=True)
            .mul(100.0)
            .round(1)
            .head(10)
        )

    hear_pct = _strip_name(pct_series(df[col_hear])) if col_hear else pd.Series(dtype=float)
    price_pct = _strip_name(pct_series(df[col_price])) if col_price else pd.Series(dtype=float)
    promo_pct = (
        _strip_name(
            df[col_promo]
            .astype(str)
            .str.strip()
            .replace("", np.nan)
            .dropna()
            .map(shorten_promo_label)
            .value_counts(normalize=True)
            .mul(100.0)
            .round(1)
            .head(8)
        )
        if col_promo
        else pd.Series(dtype=float)
    )
    age_pct = _strip_name(pct_series(df[col_age], top_n=8)) if col_age else pd.Series(dtype=float)

    team_pct = pd.Series(dtype=float)
    if col_team:
        def _team_bucket(x: str) -> str:
            x = str(x).lower()
            if "crown" in x:
                return "Charlotte Crown @ Bojangles"
            if "charlotte fc" in x or "bank of america" in x:
                return "Charlotte FC @ BofA"
            if "knights" in x or "truist" in x:
                return "Knights @ Truist"
            if "checkers" in x:
                return "Checkers @ Coliseum"
            return "Other / unclear"

        team_pct = _strip_name(
            df[col_team]
            .astype(str)
            .map(_team_bucket)
            .value_counts(normalize=True)
            .mul(100.0)
            .round(1)
        )

    star_mean: float | None = None
    star_n: int = 0
    if col_star:
        star_raw = pd.to_numeric(df[col_star], errors="coerce").dropna()
        star_n = int(len(star_raw))
        if star_n > 0:
            star_mean = float(star_raw.mean())

    return {
        "n": n,
        "columns_resolved": {
            "factor": col_factor,
            "hear": col_hear,
            "price": col_price,
            "promo": col_promo,
            "age": col_age,
            "team": col_team,
            "star": col_star,
        },
        "factor_pct": factor_pct,
        "hear_pct": hear_pct,
        "price_pct": price_pct,
        "promo_pct": promo_pct,
        "age_pct": age_pct,
        "team_pct": team_pct,
        "star_mean": star_mean,
        "star_n": star_n,
    }


def format_bullets_from_pct(series: pd.Series, max_lines: int = 6, prefix: str = "• ") -> str:
    lines = []
    for lab, pct in series.items():
        lines.append(f"{prefix}{lab} — {pct:.0f}%")
        if len(lines) >= max_lines:
            break
    return "\n".join(lines) if lines else "• (no responses)"


def reformat_hear_bullets(series: pd.Series, max_lines: int = 6) -> str:
    lines = []
    for lab, pct in series.items():
        lines.append(f"• {shorten_hear_label(str(lab))} — {pct:.0f}%")
        if len(lines) >= max_lines:
            break
    return "\n".join(lines) if lines else "• (no responses)"
