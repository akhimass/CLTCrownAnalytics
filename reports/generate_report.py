# reports/generate_report.py
"""
Build a single markdown analytics report from live model outputs.

Run standalone:
    python -m reports.generate_report
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from config.settings import settings
from config.constants import CROWN_DRIVER_WEIGHTS_PRIOR, DRIVER_WEIGHTS_PRIOR
from models.revenue_model import RevenueModel, STRATEGY_A_PROMOS
from models.cannibalization import CannibalizationAnalyzer
from pipelines.transit_features import (
    transit_summary,
    shuttle_impact_estimate,
    compute_transit_penalty,
)
from pipelines.build_master_calendar import build_master
from models.scenario_simulator import simulate_scenario_dict

logger = logging.getLogger(__name__)


def _markdown_table(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavored markdown table (no extra deps)."""
    if df.empty:
        return "_No rows._"
    cols = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for _, row in df.iterrows():
        cells = []
        for c in df.columns:
            v = row[c]
            if pd.isna(v):
                cells.append("")
            else:
                cells.append(str(v).replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _load_mlr_rf():
    """Load trained models from disk, fitting on synthetic data only if missing."""
    from models.attendance_mlr import AttendanceMLR
    from models.random_forest_model import AttendanceRF

    mlr_path = settings.DATA_PROCESSED / "mlr_model.pkl"
    rf_path = settings.DATA_PROCESSED / "rf_model.pkl"
    mlr = None
    rf = None
    if mlr_path.exists():
        try:
            mlr = AttendanceMLR.load(mlr_path)
        except Exception as exc:
            logger.warning("MLR pickle unloadable (%s); refitting", exc)
    if rf_path.exists():
        try:
            rf = AttendanceRF.load(rf_path)
        except Exception as exc:
            logger.warning("RF pickle unloadable (%s); refitting", exc)
    if mlr is None:
        mlr = AttendanceMLR()
        mlr.fit()
    train_df = mlr.load_training_data()
    if rf is None:
        rf = AttendanceRF()
        rf.fit(train_df)
    return mlr, rf


def _feature_to_driver_narrative(feature: str) -> str:
    """Map MLR feature name to business driver label."""
    m = {
        "has_promo": "Promotions & theme nights",
        "promo_multiplier": "Promotions (intensity)",
        "opponent_tier": "Star player / opponent quality",
        "is_weekend": "Weekend / leisure timing",
        "is_evening": "Evening slot",
        "game_number": "Season schedule position",
        "transit_score": "Transportation / transit access",
        "month": "Season month",
        "is_bad_weather": "Game-day weather",
        "concession_value_index": "Concession value (lower = better)",
        "has_bundle_offer": "Concession bundle offer",
        "school_session_score": "University session / summer calendar",
        "is_holiday_weekend": "Holiday weekend timing",
        "competing_event_score": "Competing Charlotte events",
        "social_buzz_score": "Social / schedule buzz proxy",
        "parking_avg_cost": "Parking cost level",
        "parking_free": "Free parking (Crown)",
        "total_coa_vs_fc": "Total COA advantage vs FC",
    }
    return m.get(feature, feature.replace("_", " ").title())


def _confidence_label(p_val: Optional[float]) -> str:
    if p_val is None or pd.isna(p_val):
        return "Model / prior"
    return "High (p<0.05)" if float(p_val) < 0.05 else "Moderate"


def build_report_markdown() -> str:
    """
    Assemble the full Crown analytics markdown report from pipeline outputs.

    Returns:
        Complete markdown document as a string.
    """
    mlr, rf = _load_mlr_rf()
    revenue = RevenueModel()
    revenue.run_all()
    uplift = revenue.uplift_table()

    cann = CannibalizationAnalyzer()
    cann_results = cann.run_all()
    crown_rows = cann.crown_impact_estimate()

    master = build_master(save=False)
    transit_df = transit_summary()
    shuttle = shuttle_impact_estimate()
    penalty = compute_transit_penalty("crown", "fc")

    from viz.revenue_charts import plot_shuttle_roi, plot_driver_comparison_mlr_vs_rf

    plot_shuttle_roi(save=True)
    plot_driver_comparison_mlr_vs_rf(mlr, rf, save=True)

    drivers = mlr.driver_summary().head(3)
    ols_r2 = float(mlr.ols_result.rsquared) if mlr.ols_result is not None else float("nan")
    rf_rank = rf.driver_ranking()

    # Executive bullets from live summaries
    base_rev = float(revenue.scenarios["baseline"].total_revenue)
    strat_a_rev = float(revenue.scenarios["strategy_a"].total_revenue)
    strat_b_rev = float(revenue.scenarios["strategy_b"].total_revenue)
    crown_fc = cann_results[
        (cann_results["team_affected"] == "charlotte_crown")
        & (cann_results["team_causing_conflict"] == "charlotte_fc")
    ]
    crown_k = cann_results[
        (cann_results["team_affected"] == "charlotte_crown")
        & (cann_results["team_causing_conflict"] == "charlotte_knights")
    ]
    fc_pct = float(crown_fc["delta_pct"].iloc[0]) if not crown_fc.empty else -18.0
    kn_pct = float(crown_k["delta_pct"].iloc[0]) if not crown_k.empty else -9.0

    lines = []
    lines.append("# Charlotte Crown — Analytics Report (2026 season preview)\n")
    lines.append("\n## Executive summary\n")
    lines.append(
        f"- **Revenue upside**: Strategy A projects **${strat_a_rev:,.0f}** season revenue vs. "
        f"baseline **${base_rev:,.0f}**; Strategy B **${strat_b_rev:,.0f}** (from `RevenueModel`).\n"
    )
    lines.append(
        f"- **Cannibalization**: Same-night **Charlotte FC** is associated with roughly **{fc_pct:.0f}%** "
        f"lower Crown attendance in the synthetic/historical bridge model; **Knights** about **{kn_pct:.0f}%**.\n"
    )
    lines.append(
        f"- **Transit gap**: Crown (Bojangles) faces about **+{penalty:.1f} minutes** weighted average "
        f"extra travel vs. Bank of America Stadium from key transit-dependent zips (`transit_features`).\n"
    )
    lines.append(
        f"- **Shuttle economics**: Estimated **{shuttle['roi_pct']:.0f}%** net ROI on a **${shuttle['season_shuttle_cost']:,.0f}** "
        f"season shuttle budget vs. **${shuttle['gross_revenue_uplift']:,.0f}** gross incremental revenue.\n"
    )
    lines.append(
        f"- **Driver model fit (MLR)**: OLS R² = **{ols_r2:.3f}** on normalized FC+Knights fill rates — "
        "interpretable ranking; RF used second for non-linear validation (`random_forest_model`).\n"
    )

    lines.append("\n## Top attendance drivers (MLR, top 3 by |coefficient| share)\n")
    driver_rows = []
    for rank, (_, row) in enumerate(drivers.iterrows(), start=1):
        feat = str(row["feature"])
        label = _feature_to_driver_narrative(feat)
        wp = row["weight_pct"]
        ev = (
            f"coef={row['coefficient']:.4f}, p={row['p_value']:.4g}"
            if pd.notna(row.get("p_value"))
            else "prior-aligned feature"
        )
        conf = _confidence_label(row.get("p_value"))
        driver_rows.append(
            {"Rank": rank, "Driver": label, "Weight %": f"{wp}%", "Evidence": ev, "Confidence": conf}
        )
    lines.append(_markdown_table(pd.DataFrame(driver_rows)))
    lines.append(
        f"\n*FC/Knights literature priors (`constants.DRIVER_WEIGHTS_PRIOR`):* "
        f"{', '.join(f'{k}={v:.0%}' for k, v in DRIVER_WEIGHTS_PRIOR.items())}.\n"
    )
    lines.append(
        f"\n*Crown Year 1 survey-corrected priors (`constants.CROWN_DRIVER_WEIGHTS_PRIOR`):* "
        f"{', '.join(f'{k}={v:.0%}' for k, v in CROWN_DRIVER_WEIGHTS_PRIOR.items())}.\n"
    )

    lines.append("\n## Revenue scenarios (live `RevenueModel` outputs)\n")
    summ = revenue.run_all()
    lines.append(_markdown_table(summ))
    lines.append("\n**Why the uplift moves:**\n")
    lines.append(
        "- **Strategy A** layers promo multipliers on a higher base fill (`STRATEGY_FILL_RATE`), "
        "discount/anchor pricing on select nights, and higher ancillary spend per head.\n"
    )
    lines.append(
        "- **Strategy B** adds the CTC→Bojangles shuttle program lift on top of Strategy A attendance.\n"
    )
    lines.append("\n**Uplift vs. baseline:**\n")
    lines.append(_markdown_table(uplift))

    lines.append("\n## Game-by-game conflict risk (all Crown home games)\n")
    mcols = master[
        [
            c
            for c in [
                "date",
                "opponent",
                "hour",
                "conflict_risk",
                "fc_same_day",
                "knights_same_day",
                "cannibalization_pct",
                "fc_opponent",
                "knights_opponent",
            ]
            if c in master.columns
        ]
    ]
    lines.append(_markdown_table(mcols))

    lines.append("\n## Cannibalization — what it means for scheduling\n")
    lines.append(_markdown_table(cann_results))
    lines.append(
        "\n**Interpretation:** nights when FC or Knights also draw the Charlotte sports "
        "entertainment dollar compress Crown trial — lead with stronger promos/pricing and "
        "transit ease on those dates rather than expecting organic walk-up.\n"
    )

    lines.append("\n## Transit gap & shuttle ROI\n")
    lines.append(_markdown_table(transit_df))
    lines.append("\n**Shuttle scenario (defaults in `shuttle_impact_estimate`):**\n")
    lines.append(_markdown_table(pd.DataFrame([shuttle]).T.reset_index().rename(columns={0: "value"})))
    lines.append(
        "\n**Parking & total cost of attendance:** Crown's free parking at Bojangles Coliseum provides "
        "a **~$35 per-person** cost advantage vs. FC (uptown parking avg **$35**) and **~$15** vs. Knights. "
        "Combined with lower ticket prices, total cost of attendance is **$40–$51 cheaper per person** than "
        "an FC game (see `TOTAL_COA_ADVANTAGE` in `constants`), which is the single strongest "
        "value-proposition marketing message available to the Crown in Year 1.\n"
    )

    lines.append("\n## Value proposition — illustrative night out for two\n")
    lines.append(
        "Using the same ticket + parking + average concession framing as the strategy model "
        "(Crown **$14** tickets, **$0** parking; FC **$30** + **$35** parking; Knights **$18** + **$15** parking; "
        "concession spend per person from `COA_CONCESSION_AVG_PER_PERSON`):\n"
    )
    lines.append(
        _markdown_table(
            pd.DataFrame(
                [
                    {
                        "Venue": "Crown @ Bojangles",
                        "Tickets (2)": "$28",
                        "Parking": "$0",
                        "Concessions (2)": "$36",
                        "Total": "$64",
                    },
                    {
                        "Venue": "Charlotte FC @ BofA",
                        "Tickets (2)": "$60",
                        "Parking": "$35",
                        "Concessions (2)": "$44",
                        "Total": "$139",
                    },
                    {
                        "Venue": "Knights @ Truist",
                        "Tickets (2)": "$36",
                        "Parking": "$15",
                        "Concessions (2)": "$30",
                        "Total": "$81",
                    },
                ]
            )
        )
    )
    lines.append(
        "\nCrown is about **54% cheaper than FC** and **~21% cheaper than Knights** for this "
        "illustrative couple night out — driven by **free parking**, lower tickets, and a lower "
        "concession value index vs. uptown stadiums.\n"
    )

    lines.append("\n## Recommended promo calendar (Strategy A mapping)\n")
    promo_rows = []
    for date_str, (ptype, label) in sorted(STRATEGY_A_PROMOS.items()):
        promo_rows.append({"date": date_str, "promo_type": ptype, "description": label})
    lines.append(_markdown_table(pd.DataFrame(promo_rows)))

    lines.append("\n## Before / after revenue (modeled)\n")
    lines.append(_markdown_table(uplift))
    lines.append(
        "\n**% uplift** reflects higher modeled fill, promo-driven attendance multipliers, "
        "and ancillary attach — not a guarantee of realized results.\n"
    )

    lines.append("\n## Example scenario simulation (single game)\n")
    ex = simulate_scenario_dict(
        promo_type="giveaway",
        ticket_price=12.0,
        has_shuttle=True,
        opponent="Greensboro Groove",
        day_of_week="Saturday",
        hour=19,
        prefer_mlr=True,
    )
    lines.append(f"```\n{ex}\n```\n")

    lines.append("\n## Methodology\n")
    lines.append(
        f"- **Multiple linear regression (`AttendanceMLR`)** — OLS via statsmodels for "
        f"coefficients and p-values; Ridge on standardized features for stable predictions. "
        f"**R² ({ols_r2:.3f})** is in-sample explanatory power on FC+Knights normalized attendance; "
        "it is *not* Crown-specific validation (no Crown games yet).\n"
    )
    lines.append(
        "- **Random Forest + GBM (`AttendanceRF`)** — captures non-linearities and interactions; "
        "permutation importance cross-checks the MLR ranking.\n"
    )
    lines.append(
        "- **Why MLR first, then RF:** MLR gives an interpretable signed ranking for stakeholders; "
        "RF stress-tests whether the same factors dominate when allowing flexible functional form.\n"
    )
    lines.append("\n### RF driver ranking (full table)\n")
    lines.append(_markdown_table(rf_rank))

    lines.append("\n## Charts generated with this report\n")
    lines.append("- `13_shuttle_roi.png` — shuttle cost vs. incremental revenue.\n")
    lines.append("- `14_driver_mlr_vs_rf.png` — MLR |coef| share vs. RF importance share.\n")

    return "\n".join(lines)


def write_report(path: Path | None = None) -> Path:
    """
    Write `crown_analytics_report.md` under reports/.

    Args:
        path: Optional override path.

    Returns:
        Path to the written file.
    """
    path = path or (settings.REPORTS_DIR / "crown_analytics_report.md")
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    text = build_report_markdown()
    path.write_text(text, encoding="utf-8")
    print(f"Wrote report → {path}")
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Generate Crown analytics markdown report")
    ap.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output path (default: reports/crown_analytics_report.md)",
    )
    args = ap.parse_args()
    write_report(Path(args.output) if args.output else None)
