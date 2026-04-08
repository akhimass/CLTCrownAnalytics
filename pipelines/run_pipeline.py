# pipelines/run_pipeline.py
"""
End-to-end pipeline runner.

Steps:
  1. Scrape FC, Knights, Checkers — or seed-only when config SPORTS_SEED_ONLY
  2. Engineer features
  3. Build master calendar + conflict flags
  4. Train MLR + RF models
  5. Run cannibalization analysis
  6. Run revenue model (all scenarios)
  7. Generate all visualizations
  8. Export CSVs to data/processed/

Usage:
    python -m pipelines.run_pipeline              # full run
    python -m pipelines.run_pipeline --skip-scrape   # skip scraping, use existing data
    python -m pipelines.run_pipeline --viz-only      # only regenerate charts
    python -m pipelines.run_pipeline --scrape-only   # scrape + CSVs only (no models)
"""
import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.REPORTS_DIR / "pipeline.log"),
    ],
)
logger = logging.getLogger("pipeline")


def run_scrapers():
    logger.info("── STEP 1: Scraping team game logs ──")
    from scrapers.fc_scraper import FCScraper
    from scrapers.knights_scraper import KnightsScraper
    from scrapers.checkers_scraper import CheckersScraper
    from models.feature_engineering import engineer_fc_features, engineer_knights_features
    from config.constants import SCRAPE_YEARS

    fc_scraper = FCScraper()
    fc_raw = fc_scraper.fetch_all_seasons(SCRAPE_YEARS)
    if not fc_raw.empty:
        fc_enriched = engineer_fc_features(fc_raw)
        fc_enriched.to_csv(settings.DATA_PROCESSED / "fc_games.csv", index=False)
        logger.info(f"FC: saved {len(fc_enriched)} rows")

    knights_scraper = KnightsScraper()
    knights_raw = knights_scraper.fetch_all_seasons(SCRAPE_YEARS)
    if not knights_raw.empty:
        knights_enriched = engineer_knights_features(knights_raw)
        knights_enriched.to_csv(settings.DATA_PROCESSED / "knights_games.csv", index=False)
        logger.info(f"Knights: saved {len(knights_enriched)} rows")

    checkers_scraper = CheckersScraper()
    checkers_raw = checkers_scraper.fetch_all_seasons(SCRAPE_YEARS)
    if not checkers_raw.empty:
        checkers_raw.to_csv(settings.DATA_PROCESSED / "checkers_games.csv", index=False)
        logger.info(f"Checkers: saved {len(checkers_raw)} rows")


def run_scrape_only():
    """
    Refresh FC/Knights game logs (+ optional Checkers), write data/raw then processed CSVs.

    Does not train models, build charts, or run the revenue/cannibalization steps.
    """
    logger.info("=" * 60)
    logger.info("SCRAPE-ONLY — raw payloads + processed CSVs (no models / viz / report)")
    logger.info("=" * 60)
    settings.ensure_dirs()

    from config.constants import SCRAPE_YEARS
    from models.feature_engineering import engineer_fc_features, engineer_knights_features
    from scrapers.fc_scraper import FCScraper
    from scrapers.knights_scraper import KnightsScraper
    from scrapers.opponent_quality import export_fc_opponent_quality_csv

    def _append_fc_2026(scraper, df: pd.DataFrame) -> pd.DataFrame:
        """Attach seed FC 2026 schedule (not on fbref SCRAPE_YEARS)."""
        f6 = scraper._from_seed(2026)
        if f6.empty:
            return df
        e6 = scraper._enrich(f6)
        if df.empty:
            return e6
        return pd.concat([df, e6], ignore_index=True)

    def _append_kn_2026(scraper, df: pd.DataFrame) -> pd.DataFrame:
        """Attach seed Knights 2026 when not covered by Baseball Cube IDs."""
        k6 = scraper._from_seed(2026)
        if k6.empty:
            return df
        e6 = scraper._enrich(k6)
        if df.empty:
            return e6
        return pd.concat([df, e6], ignore_index=True)

    fc_scraper = FCScraper()
    fc_raw = fc_scraper.fetch_all_seasons(SCRAPE_YEARS)
    if fc_raw.empty:
        logger.warning("FC scrape-only: empty frame; loading seed for SCRAPE_YEARS")
        frames = [fc_scraper._from_seed(y) for y in SCRAPE_YEARS]
        frames = [f for f in frames if not f.empty]
        if frames:
            fc_raw = fc_scraper._enrich(pd.concat(frames, ignore_index=True))
    fc_raw = _append_fc_2026(fc_scraper, fc_raw)
    fc_enriched = engineer_fc_features(fc_raw)
    fc_enriched.to_csv(settings.DATA_PROCESSED / "fc_games.csv", index=False)
    logger.info(f"FC: {len(fc_enriched)} rows → processed/fc_games.csv")

    kn_scraper = KnightsScraper()
    kn_raw = kn_scraper.fetch_all_seasons(SCRAPE_YEARS)
    if kn_raw.empty:
        logger.warning("Knights scrape-only: empty frame; loading seed for SCRAPE_YEARS")
        frames = [kn_scraper._from_seed(y) for y in SCRAPE_YEARS]
        frames = [f for f in frames if not f.empty]
        if frames:
            kn_raw = kn_scraper._enrich(pd.concat(frames, ignore_index=True))
    kn_raw = _append_kn_2026(kn_scraper, kn_raw)
    kn_enriched = engineer_knights_features(kn_raw)
    kn_enriched.to_csv(settings.DATA_PROCESSED / "knights_games.csv", index=False)
    logger.info(f"Knights: {len(kn_enriched)} rows → processed/knights_games.csv")

    export_fc_opponent_quality_csv()
    logger.info("Opponent quality → processed/fc_opponent_quality.csv")

    try:
        from scrapers.checkers_scraper import CheckersScraper

        ch = CheckersScraper()
        ch_raw = ch.fetch_all_seasons(SCRAPE_YEARS)
        if not ch_raw.empty:
            ch_raw.to_csv(settings.DATA_PROCESSED / "checkers_games.csv", index=False)
            logger.info(f"Checkers: {len(ch_raw)} rows → processed/checkers_games.csv")
        else:
            logger.warning("Checkers: no rows (API/parse) — checkers_games.csv not updated")
    except Exception as e:
        logger.warning(f"Checkers scrape-only skipped: {e}")

    logger.info("SCRAPE-ONLY complete.")


def run_seed_load():
    """Load seed data directly to processed/ without scraping."""
    logger.info("── STEP 1 (seed): Loading seed data ──")
    from scrapers.fc_scraper import FCScraper
    from scrapers.knights_scraper import KnightsScraper
    from models.feature_engineering import engineer_fc_features, engineer_knights_features
    from config.constants import SCRAPE_YEARS

    fc = FCScraper()
    frames = []
    for y in SCRAPE_YEARS:
        frames.append(fc._from_seed(y))
    fc_2026 = fc._from_seed(2026)
    if not fc_2026.empty:
        frames.append(fc_2026)
    fc_raw = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    logger.info(
        "FC after _from_seed: %s rows, cols=%s, has_promo in df=%s",
        len(fc_raw),
        list(fc_raw.columns),
        "has_promo" in fc_raw.columns,
    )
    fc_raw = fc._enrich(fc_raw)
    fc_promo_pre = int(fc_raw["has_promo"].sum()) if "has_promo" in fc_raw.columns else 0
    logger.info("FC after _enrich: has_promo sum=%s, promo_name non-empty=%s", fc_promo_pre, (fc_raw.get("promo_name", pd.Series(dtype=str)) != "").sum())

    fc_enriched = engineer_fc_features(fc_raw)
    fc_promo_post = int(fc_enriched["has_promo"].sum()) if "has_promo" in fc_enriched.columns else 0
    logger.info("FC after engineer_fc_features: has_promo sum=%s", fc_promo_post)

    fc_enriched.to_csv(settings.DATA_PROCESSED / "fc_games.csv", index=False)
    logger.info(f"FC seed: {len(fc_enriched)} rows → fc_games.csv")

    fc_promo_count = fc_enriched["has_promo"].sum() if "has_promo" in fc_enriched.columns else 0
    print(f"FC promo-tagged games: {fc_promo_count} (expected: ~22 across 2024-2025)")
    assert fc_promo_count >= 10, f"Promo tagging failed — only {fc_promo_count} games tagged"

    knights = KnightsScraper()
    frames = []
    for y in SCRAPE_YEARS:
        frames.append(knights._from_seed(y))
    kn_2026 = knights._from_seed(2026)
    if not kn_2026.empty:
        frames.append(kn_2026)
    k_raw = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    logger.info(
        "Knights after _from_seed: %s rows, has_promo in df=%s",
        len(k_raw),
        "has_promo" in k_raw.columns,
    )
    k_raw = knights._enrich(k_raw)
    kn_pre = int(k_raw["has_promo"].sum()) if "has_promo" in k_raw.columns else 0
    logger.info("Knights after _enrich: has_promo sum=%s", kn_pre)

    k_enriched = engineer_knights_features(k_raw)
    logger.info("Knights after engineer_knights_features: has_promo sum=%s", int(k_enriched["has_promo"].sum()) if "has_promo" in k_enriched.columns else 0)

    k_enriched.to_csv(settings.DATA_PROCESSED / "knights_games.csv", index=False)
    logger.info(f"Knights seed: {len(k_enriched)} rows → knights_games.csv")

    knights_promo_count = k_enriched["has_promo"].sum() if "has_promo" in k_enriched.columns else 0
    print(f"Knights promo-tagged games: {knights_promo_count} (expected: ~30+ with recurring promos)")
    assert knights_promo_count >= 15, f"Knights promo tagging failed — only {knights_promo_count} games tagged"


def run_weather_features():
    logger.info("── Weather: Open-Meteo archive for game dates ──")
    try:
        from pipelines.weather_features import fetch_game_weather

        fetch_game_weather(dry_run=False)
    except Exception as e:
        logger.warning("Weather pipeline failed (%s) — defaulting weather features to 0", e)
        from pipelines.weather_features import write_zero_weather_fallback

        write_zero_weather_fallback()


def run_calendar_features():
    logger.info("── Calendar: school session + holiday flags ──")
    from pipelines.calendar_features import build_calendar_features

    build_calendar_features(save=True)


def run_event_calendar():
    logger.info("── Events: competing entertainment calendar ──")
    from pipelines.event_calendar import build_event_calendar

    build_event_calendar(save=True, try_web_refresh=True)


def run_seatgeek_demand():
    logger.info("── SeatGeek: optional ticket-demand baseline ──")
    if not settings.SEATGEEK_CLIENT_ID:
        logger.warning("SEATGEEK_CLIENT_ID not set — skipping demand pull")
        return
    from scrapers.seatgeek_scraper import SeatGeekScraper, fetch_and_save_demand_baseline

    try:
        fetch_and_save_demand_baseline()
        scraper = SeatGeekScraper()
        for slug in ("charlotte-fc", "charlotte-knights-baseball"):
            score = scraper.get_performer_score(slug)
            logger.info("SeatGeek score %s: %s", slug, score.get("score"))
    except Exception as exc:
        logger.warning("SeatGeek pull failed (%s) — continuing without demand CSV", exc)


def run_roster_check():
    logger.info("── UpShot rosters: May 9+ check ──")
    from scrapers.roster_scraper import RosterScraper

    scraper = RosterScraper()
    try:
        result = scraper.scrape_all_rosters()
    except Exception as exc:
        logger.warning("Roster scrape error (%s) — treating as not live", exc)
        result = pd.DataFrame()
    if result.empty:
        logger.info("UpShot rosters not yet announced (expected May 9, 2026)")
        return
    logger.info("Found %s roster rows across teams", len(result))
    flagged = scraper.check_for_star_players(result)
    flagged.to_csv(settings.DATA_PROCESSED / "upshot_rosters.csv", index=False)
    presence = scraper.update_opponent_star_presence(flagged)
    pd.DataFrame(
        [{"team": k, **v} for k, v in presence.items()]
    ).to_csv(settings.DATA_PROCESSED / "opponent_star_flags.csv", index=False)


def run_master_calendar():
    logger.info("── STEP 2: Building master calendar ──")
    from pipelines.build_master_calendar import build_master
    master = build_master(save=True)
    logger.info(f"Master calendar: {len(master)} Crown home games")
    return master


def run_models():
    logger.info("── STEP 3: Training attendance models ──")
    from models.attendance_mlr import AttendanceMLR
    from models.random_forest_model import AttendanceRF

    mlr = AttendanceMLR()
    mlr.fit()
    mlr.save()

    drivers = mlr.driver_summary()
    drivers.to_csv(settings.DATA_PROCESSED / "driver_weights_mlr.csv", index=False)
    logger.info(f"MLR R²={mlr.ols_result.rsquared:.3f}")

    rf = AttendanceRF()
    rf.fit()
    rf.save()
    rf_importance = rf.driver_ranking()
    rf_importance.to_csv(settings.DATA_PROCESSED / "driver_weights_rf.csv", index=False)
    logger.info("RF model trained")

    return mlr, rf


def run_cannibalization():
    logger.info("── STEP 4: Cannibalization analysis ──")
    from models.cannibalization import CannibalizationAnalyzer

    analyzer = CannibalizationAnalyzer()
    results = analyzer.run_all()
    results.to_csv(settings.DATA_PROCESSED / "cannibalization_results.csv", index=False)

    impact = analyzer.crown_impact_estimate()
    impact.to_csv(settings.DATA_PROCESSED / "crown_conflict_impact.csv", index=False)

    analyzer.print_summary()
    return analyzer


def run_revenue_model():
    logger.info("── STEP 5: Revenue model ──")
    from models.revenue_model import RevenueModel

    model = RevenueModel()
    model.run_all()
    model.save()
    model.print_summary()

    uplift = model.uplift_table()
    uplift.to_csv(settings.DATA_PROCESSED / "revenue_uplift.csv", index=False)
    return model


def run_transit_analysis():
    logger.info("── STEP 6: Transit analysis ──")
    from pipelines.transit_features import transit_summary, shuttle_impact_estimate

    summary = transit_summary()
    summary.to_csv(settings.DATA_PROCESSED / "transit_summary.csv", index=False)
    logger.info(f"\n{summary.to_string()}")

    shuttle = shuttle_impact_estimate()
    pd.DataFrame([shuttle]).to_csv(settings.DATA_PROCESSED / "shuttle_impact.csv", index=False)
    logger.info(f"Shuttle net ROI: {shuttle['roi_pct']}%")


def run_visualizations(mlr=None, revenue_model=None, rf=None):
    logger.info("── STEP 7: Generating visualizations ──")
    from viz.attendance_drivers import plot_all as plot_drivers
    from viz.revenue_charts import plot_all as plot_revenue
    from viz.conflict_calendar import plot_all as plot_calendar

    if mlr is not None:
        from viz.attendance_drivers import plot_driver_weights
        plot_driver_weights(mlr.driver_summary())
    else:
        plot_drivers()

    plot_revenue(revenue_model, mlr=mlr, rf=rf)
    plot_calendar()
    logger.info("All charts saved to reports/")


def run_full_pipeline(skip_scrape: bool = False, viz_only: bool = False, write_report: bool = True):
    logger.info("=" * 60)
    logger.info("CROWN ANALYTICS PIPELINE — STARTING")
    logger.info("=" * 60)

    if viz_only:
        revenue_model = run_revenue_model()
        run_visualizations(revenue_model=revenue_model, mlr=None, rf=None)
        return

    if skip_scrape:
        run_seed_load()
    else:
        try:
            run_scrapers()
        except Exception as e:
            logger.warning(f"Scraping failed ({e}), falling back to seed data")
            run_seed_load()

    run_event_calendar()
    run_calendar_features()
    run_seatgeek_demand()
    run_roster_check()
    run_weather_features()
    run_master_calendar()
    mlr, rf = run_models()
    run_cannibalization()
    revenue_model = run_revenue_model()
    run_transit_analysis()
    run_visualizations(mlr=mlr, revenue_model=revenue_model, rf=rf)

    if write_report:
        logger.info("── STEP 8: Markdown report ──")
        from reports.generate_report import write_report

        write_report()

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE — check data/processed/ and reports/")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crown Analytics Pipeline")
    parser.add_argument("--skip-scrape", action="store_true",
                        help="Skip scraping, use seed data")
    parser.add_argument("--viz-only", action="store_true",
                        help="Only regenerate visualizations")
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only scrape FC/Knights (+ Checkers), write raw + processed CSVs; no models",
    )
    args = parser.parse_args()

    if args.scrape_only:
        run_scrape_only()
    else:
        run_full_pipeline(skip_scrape=args.skip_scrape, viz_only=args.viz_only, write_report=True)
