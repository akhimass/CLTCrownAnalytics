# scrapers/opponent_quality.py
"""
FC opponent → quality tier reference table (CSV export for scrape / refresh flows).

Crown opponent tiers for the simulator live in `models.feature_engineering.score_crown_opponent`.
"""
from pathlib import Path

import pandas as pd

from config.settings import settings
from models.feature_engineering import FC_OPPONENT_TIERS

# Columns expected in fc_opponent_quality.csv (tests rely on this contract)
FC_OPPONENT_QUALITY_COLUMNS = ("opponent", "quality_tier", "source")


def build_fc_opponent_quality_dataframe() -> pd.DataFrame:
    """
    Build a table of FC opponents with model quality tiers (1–3).

    Returns:
        Sorted DataFrame with columns opponent, quality_tier, source.
    """
    rows = []
    for opp, tier in FC_OPPONENT_TIERS.items():
        if opp == "default":
            continue
        rows.append(
            {
                "opponent": opp,
                "quality_tier": int(tier),
                "source": "feature_engineering.FC_OPPONENT_TIERS",
            }
        )
    return pd.DataFrame(rows).sort_values("opponent").reset_index(drop=True)


def export_fc_opponent_quality_csv(path: Path | None = None) -> Path:
    """
    Write fc_opponent_quality.csv for downstream tools and QA.

    Args:
        path: Output path; default data/processed/fc_opponent_quality.csv.

    Returns:
        Path written.
    """
    path = path or (settings.DATA_PROCESSED / "fc_opponent_quality.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    df = build_fc_opponent_quality_dataframe()
    df.to_csv(path, index=False)
    return path


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    p = export_fc_opponent_quality_csv()
    print(f"Wrote {p}")
