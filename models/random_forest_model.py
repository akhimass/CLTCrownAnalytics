# models/random_forest_model.py
"""
Random Forest attendance model for feature importance validation.
Complements MLR: non-linear, captures interaction effects,
produces SHAP-based driver rankings.

Run standalone:
    python -m models.random_forest_model
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import cross_val_score, KFold, GridSearchCV
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.inspection import permutation_importance

from config.settings import settings
from config.constants import RANDOM_STATE, CV_FOLDS
from models.attendance_mlr import AttendanceMLR, MLR_FEATURES

logger = logging.getLogger(__name__)

RF_HYPERPARAMS = {
    "n_estimators": [100, 200, 300],
    "max_depth": [4, 6, 8, None],
    "min_samples_leaf": [5, 10, 20],
    "max_features": ["sqrt", 0.5],
}


class AttendanceRF:
    def __init__(self, tune: bool = False):
        self.tune = tune
        self.rf = RandomForestRegressor(
            n_estimators=200,
            max_depth=6,
            min_samples_leaf=10,
            max_features="sqrt",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        self.gbm = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=RANDOM_STATE,
        )
        self.feature_names = MLR_FEATURES
        self.importances = None
        self.trained = False

    def fit(self, df: pd.DataFrame = None) -> "AttendanceRF":
        mlr_loader = AttendanceMLR()
        if df is None:
            df = mlr_loader.load_training_data()

        available = [f for f in self.feature_names if f in df.columns]
        X = df[available].fillna(0).astype(float)
        y = df["normalized_attendance"].clip(0, 1)

        if self.tune:
            logger.info("Running hyperparameter search (this takes a minute)...")
            cv = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
            gs = GridSearchCV(self.rf, RF_HYPERPARAMS, cv=cv, scoring="r2", n_jobs=-1)
            gs.fit(X, y)
            self.rf = gs.best_estimator_
            logger.info(f"Best params: {gs.best_params_}")
        else:
            self.rf.fit(X, y)

        self.gbm.fit(X, y)

        # Feature importance
        self.importances = pd.DataFrame({
            "feature": available,
            "rf_importance": self.rf.feature_importances_,
            "gbm_importance": self.gbm.feature_importances_,
        })
        self.importances["avg_importance"] = (
            self.importances["rf_importance"] + self.importances["gbm_importance"]
        ) / 2
        self.importances = self.importances.sort_values("avg_importance", ascending=False)

        # CV scores
        cv = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
        rf_cv  = cross_val_score(self.rf,  X, y, cv=cv, scoring="r2")
        gbm_cv = cross_val_score(self.gbm, X, y, cv=cv, scoring="r2")
        logger.info(f"RF  CV R²: {rf_cv.mean():.3f} ± {rf_cv.std():.3f}")
        logger.info(f"GBM CV R²: {gbm_cv.mean():.3f} ± {gbm_cv.std():.3f}")

        # Permutation importance (more reliable than impurity-based)
        perm = permutation_importance(self.rf, X, y, n_repeats=20,
                                       random_state=RANDOM_STATE, n_jobs=-1)
        self.importances["permutation_importance"] = perm.importances_mean[:len(available)]

        self.trained = True
        self._feature_names_fit = available
        return self

    def predict_ensemble(self, X: pd.DataFrame) -> np.ndarray:
        """Blend RF + GBM 50/50."""
        available = [f for f in self._feature_names_fit if f in X.columns]
        Xf = X[available].fillna(0).astype(float)
        return (0.5 * self.rf.predict(Xf) + 0.5 * self.gbm.predict(Xf)).clip(0, 1)

    def driver_ranking(self) -> pd.DataFrame:
        """Return ranked drivers with normalized weight %."""
        if self.importances is None:
            raise RuntimeError("Model not fitted")
        df = self.importances.copy()
        total = df["avg_importance"].sum()
        df["weight_pct"] = (df["avg_importance"] / total * 100).round(1)
        return df[["feature", "rf_importance", "gbm_importance",
                    "permutation_importance", "weight_pct"]]

    def try_shap(self, X_sample: pd.DataFrame = None) -> None:
        """Compute SHAP values if shap package is installed."""
        try:
            import shap
            available = [f for f in self._feature_names_fit if f in X_sample.columns]
            Xs = X_sample[available].fillna(0).astype(float)
            explainer = shap.TreeExplainer(self.rf)
            shap_values = explainer.shap_values(Xs)
            shap.summary_plot(shap_values, Xs, show=False)
            logger.info("SHAP summary plot generated")
        except ImportError:
            logger.info("shap not installed — skipping SHAP analysis")

    def print_summary(self):
        print("\n" + "="*60)
        print("RANDOM FOREST + GBM FEATURE IMPORTANCE")
        print("="*60)
        print(self.driver_ranking().to_string(index=False))

    def save(self, path: Path = None):
        import pickle
        path = path or (settings.DATA_PROCESSED / "rf_model.pkl")
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: Path = None) -> "AttendanceRF":
        import pickle
        path = path or (settings.DATA_PROCESSED / "rf_model.pkl")
        with open(path, "rb") as f:
            return pickle.load(f)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    model = AttendanceRF()
    model.fit()
    model.print_summary()
    model.save()
