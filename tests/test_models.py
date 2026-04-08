# tests/test_models.py
import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_revenue_model_baseline():
    from models.revenue_model import RevenueModel
    m = RevenueModel()
    base = m.build_baseline()
    assert len(base.games) == 17
    assert base.total_revenue > 0
    assert base.avg_fill_rate < 0.65

def test_revenue_model_strategy_uplift():
    from models.revenue_model import RevenueModel
    m = RevenueModel()
    m.run_all()
    uplift = m.uplift_table()
    # Strategy A and B should both exceed baseline
    assert all(uplift["revenue_uplift"] > 0)

def test_revenue_strategy_b_gt_a():
    from models.revenue_model import RevenueModel
    m = RevenueModel()
    m.run_all()
    rev_a = m.scenarios["strategy_a"].total_revenue
    rev_b = m.scenarios["strategy_b"].total_revenue
    assert rev_b > rev_a

def test_mlr_fits_and_predicts():
    from models.attendance_mlr import AttendanceMLR, MLR_FEATURES
    model = AttendanceMLR()
    df = model._synthetic_training_data()
    model.fit(df)
    assert model.trained
    assert model.ols_result.rsquared > 0.3

    X_test = pd.DataFrame([{f: 1 for f in MLR_FEATURES}])
    preds = model.predict(X_test)
    assert 0 <= preds[0] <= 1

def test_mlr_driver_summary():
    from models.attendance_mlr import AttendanceMLR
    model = AttendanceMLR()
    df = model._synthetic_training_data()
    model.fit(df)
    summary = model.driver_summary()
    assert "feature" in summary.columns
    assert "weight_pct" in summary.columns
    assert summary["weight_pct"].sum() > 0

def test_rf_fits():
    from models.random_forest_model import AttendanceRF
    from models.attendance_mlr import AttendanceMLR
    rf = AttendanceRF()
    mlr_loader = AttendanceMLR()
    df = mlr_loader._synthetic_training_data()
    rf.fit(df)
    assert rf.trained
    ranking = rf.driver_ranking()
    assert len(ranking) > 0

def test_crown_cannibalization_penalty_unified():
    """Additive penalty + cap; same semantics as master_calendar, revenue, simulator."""
    from config.constants import (
        CROWN_CONFLICT_PENALTY_CAP,
        crown_cannibalization_penalty,
        crown_conflict_fill_multiplier,
    )

    assert crown_cannibalization_penalty(1, 0) == pytest.approx(0.12)
    assert crown_cannibalization_penalty(0, 1) == pytest.approx(0.05)
    assert crown_cannibalization_penalty(1, 1) == pytest.approx(min(0.17, CROWN_CONFLICT_PENALTY_CAP))
    assert crown_conflict_fill_multiplier(1, 0) == pytest.approx(0.88)
    assert crown_conflict_fill_multiplier(1, 1) == pytest.approx(1.0 - crown_cannibalization_penalty(1, 1))


def test_cannibalization_synthetic():
    from models.cannibalization import CannibalizationAnalyzer
    a = CannibalizationAnalyzer()
    result = a._synthetic_result("charlotte_crown", "charlotte_fc", 3500)
    assert result["delta_fans"] < 0
    assert result["delta_pct"] < 0

def test_feature_engineering():
    from models.feature_engineering import engineer_fc_features
    df = pd.DataFrame({
        "date": pd.date_range("2024-03-01", periods=5, freq="2W"),
        "opponent": ["Atlanta United"] * 5,
        "attendance": [30000, 28000, 35000, 29000, 31000],
        "result": ["W", "D", "W", "L", "W"],
        "has_promo": [1, 0, 1, 0, 1],
        "promo_name": ["Giveaway", "", "Giveaway", "", "Theme Night"],
        "is_weekend": [1, 1, 0, 1, 0],
        "month": [3, 3, 4, 4, 5],
        "hour": [19, 14, 19, 19, 19],
        "season": [2024] * 5,
    })
    out = engineer_fc_features(df)
    assert "opponent_tier" in out.columns
    assert "promo_multiplier" in out.columns
    assert "fill_rate" in out.columns
    assert "is_bad_weather" in out.columns
    assert "concession_value_index" in out.columns
    assert "school_session_score" in out.columns

def test_transit_features():
    from pipelines.transit_features import (
        compute_total_travel, compute_transit_penalty, transit_summary
    )
    crown_time = compute_total_travel("28213", "crown")
    fc_time    = compute_total_travel("28213", "fc")
    assert crown_time > fc_time, "Crown should take longer from UNCC than FC"

    penalty = compute_transit_penalty("crown", "fc")
    assert penalty > 0, "Crown should have a positive transit penalty vs FC"

    summary = transit_summary()
    assert len(summary) == 3

def test_master_calendar_builds():
    from pipelines.build_master_calendar import build_crown_schedule, add_conflict_flags, FC_2026_HOME
    import pandas as pd
    crown = build_crown_schedule()
    assert len(crown) == 17
    fc = pd.DataFrame(FC_2026_HOME)
    fc["date"] = pd.to_datetime(fc["date"])
    crown_with_flags = add_conflict_flags(crown, fc, pd.DataFrame())
    assert "fc_same_day" in crown_with_flags.columns
    assert "conflict_risk" in crown_with_flags.columns
    assert crown_with_flags["fc_same_day"].sum() > 0  # at least one FC conflict


def test_master_calendar_seventeen_crown_rows():
    from pipelines.build_master_calendar import build_master

    master = build_master(save=False)
    assert len(master) == 17


def test_aug1_is_clean_no_fc_conflict():
    from pipelines.build_master_calendar import build_master
    import pandas as pd

    crown = build_master(save=False)
    aug1 = crown[crown["date"].dt.normalize() == pd.Timestamp("2026-08-01").normalize()]
    assert len(aug1) == 1
    assert int(aug1["fc_same_day"].iloc[0]) == 0, "Aug 1 should have no FC conflict — FC is away"
    assert float(aug1["cannibalization_pct"].iloc[0]) == 0.0


def test_conflict_flags_jun_6_aug_15_may_21():
    from pipelines.build_master_calendar import build_crown_schedule, add_conflict_flags, FC_2026_HOME
    from scrapers.seed_data import KNIGHTS_SEED_DATA
    import pandas as pd

    crown = build_crown_schedule()
    fc = pd.DataFrame(FC_2026_HOME)
    fc["date"] = pd.to_datetime(fc["date"])
    kn = pd.DataFrame(KNIGHTS_SEED_DATA[2026])
    kn["date"] = pd.to_datetime(kn["date"])
    out = add_conflict_flags(crown, fc, kn)

    def row(ds):
        return out[out["date"].dt.strftime("%Y-%m-%d") == ds].iloc[0]

    r_may21 = row("2026-05-21")
    assert int(r_may21["fc_same_day"]) == 0
    assert int(r_may21["knights_same_day"]) == 1
    assert float(r_may21["cannibalization_pct"]) == pytest.approx(0.05)

    r_may30 = row("2026-05-30")
    assert int(r_may30["knights_same_day"]) == 1
    assert int(r_may30["fc_same_day"]) == 0

    r_jun6 = row("2026-06-06")
    assert int(r_jun6["fc_same_day"]) == 0
    assert int(r_jun6["knights_same_day"]) == 0

    r_jun14 = row("2026-06-14")
    assert int(r_jun14["knights_same_day"]) == 1
    assert int(r_jun14["fc_same_day"]) == 0

    r_aug15 = row("2026-08-15")
    assert int(r_aug15["fc_same_day"]) == 1
    assert int(r_aug15["knights_same_day"]) == 0


def test_scenario_simulator_attendance_bounds():
    from models.scenario_simulator import simulate_scenario

    promos = ["none", "theme", "giveaway", "discount", "star", "community"]
    for promo in promos:
        for fc_c in (True, False):
            for k_c in (True, False):
                for shuttle in (True, False):
                    r = simulate_scenario(
                        promo_type=promo,
                        ticket_price=15.0,
                        has_shuttle=shuttle,
                        opponent="Savannah Steel",
                        day_of_week="Friday",
                        hour=19,
                        fc_conflict=fc_c,
                        knights_conflict=k_c,
                        prefer_mlr=False,
                    )
                    assert 0 <= r.projected_attendance <= 3500


def test_scenario_fc_conflict_reduces_attendance():
    from models.scenario_simulator import simulate_scenario

    clean = simulate_scenario(
        promo_type="giveaway",
        fc_conflict=False,
        knights_conflict=False,
        prefer_mlr=False,
        day_of_week="Saturday",
        hour=19,
    )
    clash = simulate_scenario(
        promo_type="giveaway",
        fc_conflict=True,
        knights_conflict=False,
        prefer_mlr=False,
        day_of_week="Saturday",
        hour=19,
    )
    assert clash.projected_attendance < clean.projected_attendance


def test_scenario_shuttle_raises_attendance():
    from models.scenario_simulator import simulate_scenario

    base = simulate_scenario(
        promo_type="none",
        has_shuttle=False,
        prefer_mlr=False,
        day_of_week="Tuesday",
        hour=14,
        fc_conflict=False,
        knights_conflict=False,
    )
    shuttled = simulate_scenario(
        promo_type="none",
        has_shuttle=True,
        prefer_mlr=False,
        day_of_week="Tuesday",
        hour=14,
        fc_conflict=False,
        knights_conflict=False,
    )
    assert shuttled.projected_attendance > base.projected_attendance


def test_generate_report_writes_non_empty(tmp_path):
    from reports.generate_report import write_report

    out = tmp_path / "crown_analytics_report.md"
    write_report(out)
    text = out.read_text(encoding="utf-8")
    assert len(text.strip()) > 200


def test_fc_opponent_quality_csv_columns(tmp_path):
    import pandas as pd
    from scrapers.opponent_quality import export_fc_opponent_quality_csv, FC_OPPONENT_QUALITY_COLUMNS

    path = tmp_path / "fc_opponent_quality.csv"
    export_fc_opponent_quality_csv(path)
    df = pd.read_csv(path)
    for col in FC_OPPONENT_QUALITY_COLUMNS:
        assert col in df.columns
    assert len(df) >= 1
    assert df["quality_tier"].between(1, 3).all()


def test_score_crown_opponent_valid_tiers():
    from models.feature_engineering import score_crown_opponent

    for name in ("Jacksonville Waves", "Savannah Steel", "Greensboro Groove"):
        t = score_crown_opponent(name)
        assert t in (1, 2, 3)


def test_fc_scraper_fallback_on_playwright_failure():
    from unittest.mock import patch
    from scrapers.fc_scraper import FCScraper

    scraper = FCScraper()
    seed = scraper._from_seed(2025)

    with patch.object(scraper, "_fetch_fbref_playwright", side_effect=Exception("403")):
        out = scraper.fetch_season(2025)

    assert len(out) == len(seed)
    assert list(out["opponent"]) == list(seed["opponent"])
    assert out["data_source"].str.startswith("seed").all()


def test_data_source_column_exists():
    """Processed CSVs must have data_source column after seed load."""
    from pipelines.run_pipeline import run_seed_load
    from config.settings import settings
    import pandas as pd

    run_seed_load()
    fc = pd.read_csv(settings.DATA_PROCESSED / "fc_games.csv")
    assert "data_source" in fc.columns
    assert fc["data_source"].notna().all()
    assert set(fc["data_source"].unique()).issubset(
        {"scraped_fbref", "scraped_baseball_cube", "seed_verified", "seed_estimated"}
    )


def test_fbref_playwright_fallback():
    """If Playwright fails (e.g. no browser installed), should fall back to seed."""
    from unittest.mock import patch
    from scrapers.fc_scraper import FCScraper

    scraper = FCScraper()
    with patch.object(
        scraper,
        "_fetch_fbref_playwright",
        side_effect=Exception("browser not found"),
    ):
        df = scraper.fetch_season(2025)
    assert not df.empty
    assert df["data_source"].str.startswith("seed").all()


def test_data_quality_report_runs():
    """data_quality.check_data_quality() should return a dict without crashing."""
    from pipelines.data_quality import check_data_quality

    result = check_data_quality(print_report=False)
    assert isinstance(result, dict)
    assert "fc_rows" in result
    assert "knights_rows" in result


def test_weather_features_columns():
    from pipelines.weather_features import fetch_game_weather

    df = fetch_game_weather(dry_run=True, save=False)
    assert "is_bad_weather" in df.columns
    assert "temp_max_f" in df.columns
    assert len(df) > 0
    assert df["temp_max_f"].between(0, 130).all()


def test_school_session_scores():
    from pipelines.calendar_features import get_school_session_score
    import pandas as pd

    assert get_school_session_score(pd.Timestamp("2026-05-10")) == 0.0
    assert get_school_session_score(pd.Timestamp("2026-05-21")) == 0.4
    assert get_school_session_score(pd.Timestamp("2026-06-15")) == 0.4
    assert get_school_session_score(pd.Timestamp("2026-10-01")) == 1.0


def test_competing_event_score():
    from pipelines.event_calendar import get_competition_score

    assert get_competition_score("2026-05-31") < 1.0
    assert get_competition_score("2026-05-21") == 1.0
    assert get_competition_score("2026-06-09") < 0.90


def test_parking_crown_is_free():
    from config.constants import PARKING_COSTS

    assert PARKING_COSTS["crown"]["free"] is True
    assert PARKING_COSTS["crown"]["avg"] == 0


def test_total_coa_crown_cheaper_than_fc():
    from config.constants import TOTAL_COA_ADVANTAGE

    assert TOTAL_COA_ADVANTAGE["crown_vs_fc"] > 30
    assert TOTAL_COA_ADVANTAGE["crown_vs_knights"] > 0


def test_school_session_crown_opener():
    from pipelines.calendar_features import get_school_session_score
    import pandas as pd

    score = get_school_session_score(pd.Timestamp("2026-05-21"))
    assert score == 0.4


def test_roster_scraper_handles_not_live():
    from unittest.mock import patch
    from scrapers.roster_scraper import RosterScraper

    scraper = RosterScraper()
    with patch.object(
        scraper,
        "_fetch_page_playwright",
        return_value="<html>Our Roster Is Building</html>",
    ):
        result = scraper.scrape_all_rosters()
    assert result.empty


def test_social_buzz_scores_in_range():
    from pipelines.build_master_calendar import build_master

    crown = build_master(save=False)
    assert "social_buzz_score" in crown.columns
    assert crown["social_buzz_score"].between(0.5, 1.3).all()
