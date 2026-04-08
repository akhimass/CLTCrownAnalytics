# models/attendance_mlr.py
"""
Multiple Linear Regression attendance model.
Trained on FC + Knights 3-year data.
Used to: (1) rank driver coefficients, (2) predict Crown baseline attendance.

Run standalone:
    python -m models.attendance_mlr
"""
import logging
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import cross_val_score, KFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error
import statsmodels.api as sm

from config.settings import settings
from config.constants import RANDOM_STATE, CV_FOLDS
from models.feature_engineering import engineer_fc_features, engineer_knights_features

logger = logging.getLogger(__name__)

# Features used in the regression (subset used if columns missing in training data)
MLR_FEATURES = [
    "has_promo",
    "promo_multiplier",
    "opponent_tier",
    "is_weekend",
    "is_evening",
    "game_number",
    "transit_score",
    "month",
    "is_bad_weather",
    "concession_value_index",
    "has_bundle_offer",
    "school_session_score",
    "is_holiday_weekend",
    "competing_event_score",
    "social_buzz_score",
    "parking_avg_cost",
    "parking_free",
    "total_coa_vs_fc",
]


class AttendanceMLR:
    """
    OLS regression with statsmodels for interpretable coefficients + p-values.
    Also fits sklearn Ridge for prediction.
    """

    def __init__(self):
        self.ols_result = None
        self.ridge = Ridge(alpha=1.0)
        self.scaler = StandardScaler()
        self.feature_names = MLR_FEATURES
        self.trained = False
        self.team_baselines = {}

    def load_training_data(self) -> pd.DataFrame:
        """Load processed FC + Knights data, normalize attendance to fill_rate."""
        frames = []
        for team, capacity in [("fc", 38_000), ("knights", 10_200)]:
            path = settings.DATA_PROCESSED / f"{team}_games.csv"
            if path.exists():
                df = pd.read_csv(path, parse_dates=["date"])
                engineer = engineer_fc_features if team == "fc" else engineer_knights_features
                df = engineer(df)
                df["normalized_attendance"] = df["attendance"] / capacity
                df["team"] = team
                frames.append(df)
                logger.info(f"Loaded {len(df)} {team} rows for training")
            else:
                logger.warning(f"No data for {team} — run scrapers first")

        if not frames:
            logger.warning("No processed data found — generating synthetic training data")
            return self._synthetic_training_data()

        combined = pd.concat(frames, ignore_index=True)
        if "data_source" in combined.columns:
            logger.info("Training data provenance:\n%s", combined["data_source"].value_counts().to_string())
        return combined

    def fit(self, df: pd.DataFrame = None) -> "AttendanceMLR":
        if df is None:
            df = self.load_training_data()

        available = [f for f in self.feature_names if f in df.columns]
        missing = [f for f in self.feature_names if f not in df.columns]
        if missing:
            logger.warning(
                "Training data missing optional MLR features (using subset): %s",
                missing,
            )
        self._fitted_features = list(available)
        X = df[available].fillna(0)
        y = df["normalized_attendance"].clip(0, 1)

        # Store team baselines
        for team in df["team"].unique():
            self.team_baselines[team] = df[df["team"] == team]["normalized_attendance"].mean()

        # OLS with statsmodels for coefficients + significance
        X_const = sm.add_constant(X.astype(float))
        self.ols_result = sm.OLS(y, X_const).fit()
        logger.info(f"OLS R²={self.ols_result.rsquared:.3f}")

        # Ridge for prediction (ndarray avoids sklearn feature-name / column-count drift)
        X_scaled = self.scaler.fit_transform(X.astype(float).to_numpy())
        self.ridge.fit(X_scaled, y)

        cv = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
        cv_scores = cross_val_score(self.ridge, X_scaled, y, cv=cv, scoring="r2")
        logger.info(f"Ridge CV R²: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

        self.trained = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        cols = getattr(self, "_fitted_features", None) or [
            f for f in self.feature_names if f in X.columns
        ]
        X_sub = X.reindex(columns=cols, fill_value=0)[cols].fillna(0).astype(float)
        X_scaled = self.scaler.transform(X_sub.to_numpy())
        return self.ridge.predict(X_scaled).clip(0, 1)

    def driver_summary(self) -> pd.DataFrame:
        """Return coefficient table with p-values for interpretability."""
        if self.ols_result is None:
            raise RuntimeError("Model not fitted yet")

        params = self.ols_result.params
        pvalues = self.ols_result.pvalues
        conf = self.ols_result.conf_int()

        df = pd.DataFrame({
            "feature": params.index,
            "coefficient": params.values,
            "p_value": pvalues.values,
            "ci_lower": conf[0].values,
            "ci_upper": conf[1].values,
            "significant": pvalues.values < 0.05,
        }).query("feature != 'const'").sort_values("coefficient", ascending=False)

        # Normalize coefficients to derive relative weights
        total = df["coefficient"].abs().sum()
        df["weight_pct"] = (df["coefficient"].abs() / total * 100).round(1)

        return df.reset_index(drop=True)

    def print_summary(self):
        print("\n" + "="*60)
        print("ATTENDANCE DRIVER REGRESSION SUMMARY")
        print("="*60)
        print(self.ols_result.summary())
        print("\nDRIVER WEIGHTS (derived from |coefficient| share):")
        print(self.driver_summary()[["feature", "coefficient", "p_value", "weight_pct"]].to_string(index=False))

    def save(self, path: Path = None):
        import pickle
        path = path or (settings.DATA_PROCESSED / "mlr_model.pkl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info(f"Model saved → {path}")

    @classmethod
    def load(cls, path: Path = None) -> "AttendanceMLR":
        import pickle
        path = path or (settings.DATA_PROCESSED / "mlr_model.pkl")
        with open(path, "rb") as f:
            return pickle.load(f)

    def _synthetic_training_data(self) -> pd.DataFrame:
        """
        Generate realistic synthetic data for model development when scraped
        data is not yet available. Based on FC/Knights historical averages.
        """
        np.random.seed(RANDOM_STATE)
        n = 200

        has_promo     = np.random.binomial(1, 0.35, n)
        promo_mult    = np.where(has_promo, np.random.uniform(1.1, 1.25, n), 1.0)
        opponent_tier = np.random.choice([1, 2, 3], n, p=[0.70, 0.25, 0.05])
        is_weekend    = np.random.binomial(1, 0.55, n)
        is_evening    = np.random.binomial(1, 0.75, n)
        game_number   = np.random.randint(1, 80, n)
        transit_score = np.random.choice([1, 2], n, p=[0.3, 0.7])
        month         = np.random.randint(3, 11, n)
        is_bad_weather = np.random.binomial(1, 0.12, n)
        concession_value_index = np.random.uniform(0.45, 1.0, n)
        has_bundle_offer = np.random.binomial(1, 0.08, n)
        school_session_score = np.random.choice([0.0, 0.4, 1.0], n, p=[0.15, 0.35, 0.5])
        is_holiday_weekend = np.random.binomial(1, 0.04, n)
        competing_event_score = np.random.choice([1.0, 0.93, 0.82], n, p=[0.88, 0.07, 0.05])
        social_buzz_score = np.random.uniform(0.55, 1.12, n)
        parking_avg_cost = np.random.choice([0.0, 15.0, 35.0], n, p=[0.45, 0.35, 0.2])
        parking_free = (parking_avg_cost <= 0).astype(int)
        total_coa_vs_fc = np.where(parking_free.astype(bool), 51.0, 0.0)

        # True DGP (data-generating process)
        baseline = 0.70
        noise = np.random.normal(0, 0.06, n)
        fill_rate = (
            baseline
            + 0.08 * has_promo
            + 0.04 * (promo_mult - 1)
            + 0.05 * (opponent_tier - 1)
            + 0.04 * is_weekend
            + 0.02 * is_evening
            - 0.001 * (game_number - 40)
            + 0.03 * (transit_score - 1)
            - 0.02 * is_bad_weather
            + 0.08 * (0.55 - concession_value_index)
            + 0.02 * has_bundle_offer
            + 0.015 * school_session_score
            + 0.02 * is_holiday_weekend
            + 0.04 * (competing_event_score - 1.0)
            + 0.03 * (social_buzz_score - 0.8)
            - 0.0008 * parking_avg_cost
            + 0.015 * total_coa_vs_fc / 51.0
            + noise
        ).clip(0.2, 1.05)

        return pd.DataFrame({
            "has_promo":     has_promo,
            "promo_multiplier": promo_mult,
            "opponent_tier": opponent_tier,
            "is_weekend":    is_weekend,
            "is_evening":    is_evening,
            "game_number":   game_number,
            "transit_score": transit_score,
            "month":         month,
            "is_bad_weather": is_bad_weather,
            "concession_value_index": concession_value_index,
            "has_bundle_offer": has_bundle_offer,
            "school_session_score": school_session_score,
            "is_holiday_weekend": is_holiday_weekend,
            "competing_event_score": competing_event_score,
            "social_buzz_score": social_buzz_score,
            "parking_avg_cost": parking_avg_cost,
            "parking_free": parking_free,
            "total_coa_vs_fc": total_coa_vs_fc,
            "normalized_attendance": fill_rate.clip(0, 1),
            "attendance":    (fill_rate * 30_000).astype(int),
            "team":          np.random.choice(["fc", "knights"], n),
            "data_source":   np.repeat("synthetic", n),
        })


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    model = AttendanceMLR()
    model.fit()
    model.print_summary()
    model.save()
