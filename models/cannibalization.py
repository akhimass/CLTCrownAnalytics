# models/cannibalization.py
import logging
from typing import Tuple
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from config.settings import settings
from config.constants import VENUES

logger = logging.getLogger(__name__)


class CannibalizationAnalyzer:
    def __init__(self):
        self.results = None

    def load_master(self):
        path = settings.DATA_PROCESSED / "master_calendar.csv"
        if not path.exists():
            raise FileNotFoundError(f"No master_calendar.csv at {path}")
        return pd.read_csv(path, parse_dates=["date"])

    def analyze_pair(self, master, team_a, team_b, capacity_a):
        a = master[master["team"] == team_a].copy() if "team" in master.columns else pd.DataFrame()
        if a.empty or "attendance" not in a.columns:
            return self._synthetic_result(team_a, team_b, capacity_a)

        b_dates = set(master[master.get("team", pd.Series()) == team_b]["date"].dt.normalize()) \
            if "team" in master.columns else set()
        a["conflict"] = a["date"].dt.normalize().isin(b_dates).astype(int)

        conflict    = a[a["conflict"] == 1]["attendance"].dropna()
        no_conflict = a[a["conflict"] == 0]["attendance"].dropna()

        if len(conflict) < 3 or len(no_conflict) < 3:
            return self._synthetic_result(team_a, team_b, capacity_a)

        mean_no   = no_conflict.mean()
        mean_with = conflict.mean()
        delta_abs = mean_with - mean_no
        delta_pct = delta_abs / mean_no if mean_no > 0 else 0
        t_stat, p_value = stats.ttest_ind(conflict, no_conflict)

        ctrl = [c for c in ["has_promo", "is_weekend"] if c in a.columns]
        X = sm.add_constant(a[["conflict"] + ctrl].fillna(0).astype(float))
        y = a["attendance"].fillna(mean_no)
        try:
            ols = sm.OLS(y, X).fit()
            ols_coef = float(ols.params.get("conflict", delta_abs))
            ols_pval = float(ols.pvalues.get("conflict", p_value))
        except Exception:
            ols_coef, ols_pval = delta_abs, p_value

        return {
            "team_affected": team_a, "team_causing_conflict": team_b,
            "n_conflict_games": len(conflict), "n_no_conflict_games": len(no_conflict),
            "mean_attendance_clean": round(mean_no), "mean_attendance_conflict": round(mean_with),
            "delta_fans": round(delta_abs), "delta_pct": round(delta_pct * 100, 1),
            "t_statistic": round(t_stat, 3), "p_value": round(p_value, 4),
            "ols_coefficient": round(ols_coef), "ols_p_value": round(ols_pval, 4),
            "significant": p_value < 0.05,
        }

    def _synthetic_result(self, team_a, team_b, capacity_a):
        from config.constants import CANNIBALIZATION
        a_key = team_a.replace("charlotte_", "")
        b_key = team_b.replace("charlotte_", "")
        key   = f"{a_key}_loss_when_{b_key}"
        pct   = CANNIBALIZATION.get(key, -0.07)
        base  = capacity_a * 0.65
        delta = int(base * pct)
        return {
            "team_affected": team_a, "team_causing_conflict": team_b,
            "n_conflict_games": 0, "n_no_conflict_games": 0,
            "mean_attendance_clean": int(base), "mean_attendance_conflict": int(base + delta),
            "delta_fans": delta, "delta_pct": round(pct * 100, 1),
            "t_statistic": None, "p_value": None,
            "ols_coefficient": delta, "ols_p_value": None,
            "significant": None, "source": "model_estimate",
        }

    def run_all(self):
        try:
            master = self.load_master()
        except FileNotFoundError:
            master = pd.DataFrame()

        pairs = [
            ("charlotte_fc",      "charlotte_knights", 38_000),
            ("charlotte_knights", "charlotte_fc",      10_200),
            ("charlotte_crown",   "charlotte_fc",       3_500),
            ("charlotte_crown",   "charlotte_knights",  3_500),
        ]

        rows = []
        for a, b, cap in pairs:
            r = self.analyze_pair(master, a, b, cap) if not master.empty \
                else self._synthetic_result(a, b, cap)
            if r:
                rows.append(r)

        self.results = pd.DataFrame(rows)
        return self.results

    def print_summary(self):
        if self.results is None or self.results.empty:
            self.run_all()
        print("\n" + "="*60)
        print("CANNIBALIZATION ANALYSIS")
        print("="*60)
        cols = ["team_affected", "team_causing_conflict",
                "mean_attendance_clean", "delta_fans", "delta_pct", "significant"]
        print(self.results[[c for c in cols if c in self.results.columns]].to_string(index=False))

    def crown_impact_estimate(self):
        from pipelines.build_master_calendar import build_master, CROWN_HOME_GAMES
        try:
            master_path = settings.DATA_PROCESSED / "master_calendar.csv"
            crown = pd.read_csv(master_path, parse_dates=["date"]) if master_path.exists() \
                else build_master(save=False)
        except Exception:
            crown = build_master(save=False)

        from config.constants import crown_cannibalization_penalty

        def get_penalty(row):
            if "cannibalization_pct" in row.index and pd.notna(row.get("cannibalization_pct")):
                return float(row["cannibalization_pct"]) * 100.0
            return crown_cannibalization_penalty(
                int(row.get("fc_same_day", 0)),
                int(row.get("knights_same_day", 0)),
            ) * 100.0

        base = int(3_500 * 0.65)
        crown["est_base_attendance"]    = base
        crown["conflict_penalty_pct"]   = crown.apply(get_penalty, axis=1)
        crown["est_conflict_attendance"]= (base * (1 - crown["conflict_penalty_pct"] / 100)).astype(int)
        crown["fans_lost_to_conflict"]  = base - crown["est_conflict_attendance"]

        keep = [c for c in ["date", "opponent", "conflict_risk", "fc_same_day",
                             "knights_same_day", "conflict_penalty_pct",
                             "est_base_attendance", "fans_lost_to_conflict",
                             "est_conflict_attendance"] if c in crown.columns]
        return crown[keep]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    a = CannibalizationAnalyzer()
    a.run_all()
    a.print_summary()
    print("\nCrown game-level impact:")
    print(a.crown_impact_estimate().to_string())
