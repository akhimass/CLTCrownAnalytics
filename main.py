# main.py
"""
Crown Analytics — entry point.

Quick commands:
    python main.py                          # full pipeline (seed data)
    python main.py --scrape                 # attempt live scraping first
    python main.py --viz-only              # regenerate charts only
    python main.py --no-report             # full pipeline without markdown report
    python main.py --simulate              # after pipeline, print sample scenario output
    python main.py --scrape-only           # refresh scrapes + CSVs only (no models/charts)
    python main.py --check-data            # data quality report (no pipeline)
    python main.py --revenue               # just revenue model + print
    python main.py --cannibalization       # just cannibalization analysis
    python main.py --transit               # just transit analysis
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("main")


def main():
    parser = argparse.ArgumentParser(
        description="Charlotte Crown Attendance & Revenue Analytics"
    )
    parser.add_argument("--scrape",          action="store_true", help="Live scrape mode")
    parser.add_argument("--viz-only",        action="store_true", help="Viz only")
    parser.add_argument("--revenue",         action="store_true", help="Revenue model only")
    parser.add_argument("--cannibalization", action="store_true", help="Cannibalization only")
    parser.add_argument("--transit",         action="store_true", help="Transit analysis only")
    parser.add_argument("--models",          action="store_true", help="Train models only")
    parser.add_argument(
        "--report",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="After full pipeline, write reports/crown_analytics_report.md (default: on)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="After full pipeline, print a sample scenario_simulator projection",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="Only run scrapers + save processed CSVs (no models, charts, or report)",
    )
    parser.add_argument(
        "--check-data",
        action="store_true",
        help="Print data quality / provenance report without running the pipeline",
    )
    args = parser.parse_args()

    if args.check_data:
        from pipelines.data_quality import check_data_quality

        check_data_quality(print_report=True)
        return

    if args.scrape_only:
        from pipelines.run_pipeline import run_scrape_only

        run_scrape_only()

    elif args.revenue:
        from models.revenue_model import RevenueModel
        m = RevenueModel()
        m.print_summary()
        m.save()

    elif args.cannibalization:
        from models.cannibalization import CannibalizationAnalyzer
        a = CannibalizationAnalyzer()
        a.run_all()
        a.print_summary()
        print("\nCrown game-level impact:")
        print(a.crown_impact_estimate().to_string())

    elif args.transit:
        from pipelines.transit_features import transit_summary, shuttle_impact_estimate, compute_transit_penalty
        print("\nTransit comparison:")
        print(transit_summary().to_string())
        penalty = compute_transit_penalty("crown", "fc")
        print(f"\nCrown transit penalty vs FC: +{penalty:.1f} min")
        print("\nShuttle ROI estimate:")
        for k, v in shuttle_impact_estimate().items():
            print(f"  {k}: {v}")

    elif args.models:
        from models.attendance_mlr import AttendanceMLR
        from models.random_forest_model import AttendanceRF
        mlr = AttendanceMLR()
        mlr.fit()
        mlr.print_summary()
        rf = AttendanceRF()
        rf.fit()
        rf.print_summary()

    else:
        from pipelines.run_pipeline import run_full_pipeline
        from models.scenario_simulator import simulate_scenario, _format_outcome

        run_full_pipeline(
            skip_scrape=not args.scrape,
            viz_only=args.viz_only,
            write_report=args.report,
        )
        if args.simulate:
            sample = simulate_scenario(
                promo_type="giveaway",
                ticket_price=12.0,
                has_shuttle=True,
                opponent="Greensboro Groove",
                day_of_week="Saturday",
                hour=19,
            )
            print("\nSample scenario simulation:")
            print(_format_outcome(sample))


if __name__ == "__main__":
    main()
