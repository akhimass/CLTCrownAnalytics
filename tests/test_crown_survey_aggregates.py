"""Crown Google Form survey → P12 aggregates."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_aggregates_from_sample_csv(tmp_path):
    from pipelines.crown_survey_aggregates import aggregates_for_p12, load_crown_survey_csv

    csv = tmp_path / "mini.csv"
    csv.write_text(
        "Timestamp,What is your age?,Q factor,Q hear,Q price\n"
        "1/1/2026,18-25,Price,Online - Social Media,$10 - $20\n"
        "1/2/2026,18-25,Price,Family/Friend reccomendation,<$10\n"
        "1/3/2026,26-35,Game (or Team) Quality,Online - Social Media,$10 - $20\n",
        encoding="utf-8",
    )
    df = load_crown_survey_csv(csv)
    assert len(df) == 3
    df2 = df.rename(
        columns={
            "Q factor": "Overall, when going to sporting events, what is the most important factor that influences your decision to go?",
            "Q hear": "Where would you be most likely to hear about Charlotte Crown games/promotional nights?",
            "Q price": "What price would you expect/be willing to pay for a Charlotte Crown game?",
        }
    )
    agg = aggregates_for_p12(df2)
    assert agg["n"] == 3
    assert not agg["factor_pct"].empty
    assert not agg["hear_pct"].empty
    assert not agg["price_pct"].empty


def test_p12_uses_repo_survey_when_present():
    from pipelines.crown_survey_aggregates import aggregates_for_p12, load_crown_survey_csv, resolve_crown_survey_csv

    path = resolve_crown_survey_csv()
    if path is None:
        pytest.skip("crown_survey_responses.csv not in repo")
    df = load_crown_survey_csv(path)
    agg = aggregates_for_p12(df)
    assert agg["n"] >= 1
    assert not agg["factor_pct"].empty
