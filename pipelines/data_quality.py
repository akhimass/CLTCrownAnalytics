# pipelines/data_quality.py
"""
Data quality / provenance report for processed CSVs (no full pipeline run).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import pandas as pd

from config.settings import settings

logger = logging.getLogger(__name__)

def _pct(part: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(round(100 * part / total))


def check_data_quality(print_report: bool = True) -> Dict[str, Any]:
    """
    Summarize row counts and data_source mix for FC/Knights CSVs; estimate MLR R².

    Args:
        print_report: When True, print a human-readable report to stdout.

    Returns:
        Dict with row counts, per-source breakdowns, optional mlr_r2, and flags.
    """
    settings.ensure_dirs()
    result: Dict[str, Any] = {
        "fc_rows": 0,
        "fc_breakdown": {},
        "knights_rows": 0,
        "knights_breakdown": {},
        "fc_opponent_quality_rows": 0,
        "master_calendar_rows": 0,
        "mlr_r2": None,
        "recommend_scrape": False,
    }

    fc_path = settings.DATA_PROCESSED / "fc_games.csv"
    if fc_path.exists():
        fc = pd.read_csv(fc_path)
        result["fc_rows"] = int(len(fc))
        if "data_source" in fc.columns:
            vc = fc["data_source"].value_counts()
            result["fc_breakdown"] = {str(k): int(v) for k, v in vc.items()}

    kn_path = settings.DATA_PROCESSED / "knights_games.csv"
    if kn_path.exists():
        kn = pd.read_csv(kn_path)
        result["knights_rows"] = int(len(kn))
        if "data_source" in kn.columns:
            vc = kn["data_source"].value_counts()
            result["knights_breakdown"] = {str(k): int(v) for k, v in vc.items()}

    oq_path = settings.DATA_PROCESSED / "fc_opponent_quality.csv"
    if oq_path.exists():
        result["fc_opponent_quality_rows"] = int(len(pd.read_csv(oq_path)))

    mc_path = settings.DATA_PROCESSED / "master_calendar.csv"
    if mc_path.exists():
        result["master_calendar_rows"] = int(len(pd.read_csv(mc_path)))

    scraped_fc = result["fc_breakdown"].get("scraped_fbref", 0)
    scraped_kn = result["knights_breakdown"].get("scraped_baseball_cube", 0)
    if result["fc_rows"] and scraped_fc / result["fc_rows"] < 0.25:
        result["recommend_scrape"] = True
    if result["knights_rows"] and scraped_kn / result["knights_rows"] < 0.25:
        result["recommend_scrape"] = True

    try:
        from models.attendance_mlr import AttendanceMLR

        m = AttendanceMLR()
        td = m.load_training_data()
        if len(td) >= 8:
            m.fit(td)
            result["mlr_r2"] = float(m.ols_result.rsquared)
    except Exception as exc:
        logger.debug("Could not fit MLR for data quality report: %s", exc)
        result["mlr_r2"] = None

    if print_report:
        _print_data_quality_report(result)

    return result


def _print_data_quality_report(result: Dict[str, Any]) -> None:
    lines = ["DATA QUALITY REPORT", ""]

    nfc = result["fc_rows"]
    lines.append(f"fc_games.csv         — {nfc} rows")
    for src, cnt in sorted(result["fc_breakdown"].items(), key=lambda x: -x[1]):
        lines.append(f"  {src}:    {cnt} rows ({_pct(cnt, nfc)}%)")
    if not result["fc_breakdown"]:
        lines.append("  (no data_source column or empty file)")

    lines.append("")
    nkn = result["knights_rows"]
    lines.append(f"knights_games.csv    — {nkn} rows")
    for src, cnt in sorted(result["knights_breakdown"].items(), key=lambda x: -x[1]):
        lines.append(f"  {src}:    {cnt} rows ({_pct(cnt, nkn)}%)")
    if not result["knights_breakdown"]:
        lines.append("  (no data_source column or empty file)")

    lines.append("")
    lines.append(f"fc_opponent_quality.csv — {result['fc_opponent_quality_rows']} rows")
    lines.append(
        f"master_calendar.csv     — {result['master_calendar_rows']} rows (all Crown home games)"
    )

    lines.append("")
    lines.append("MODEL TRAINING QUALITY")
    r2 = result.get("mlr_r2")
    if r2 is not None:
        if r2 < 0.40:
            lines.append(
                f"Current MLR R²: {r2:.3f} (low — insufficient real data variance)"
            )
            lines.append("Target R²: 0.40+ (achievable with full scraped game logs)")
        else:
            lines.append(f"Current MLR R²: {r2:.3f}")
    else:
        lines.append("Current MLR R²: (unable to fit — missing or insufficient data)")

    if result.get("recommend_scrape") or (r2 is not None and r2 < 0.40):
        lines.append("Recommend running `python main.py --scrape` or `--scrape-only` to improve data quality.")

    print("\n".join(lines))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    check_data_quality(print_report=True)
