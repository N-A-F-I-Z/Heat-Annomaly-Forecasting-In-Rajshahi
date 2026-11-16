"""Forecast models.

A   ClimatologyModel  – frequency of the event on similar calendar dates in past years.
A2  logistic(season + year) – climatology that is allowed to warm over time.
B   logistic(season + recent anomalies) – the anomaly-adjusted model from the study design.
B2  logistic(season + anomalies + year) – both signals together.

A2 and B2 are ablations: they separate the value of the long-term warming signal from
the value of short-term anomaly persistence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import assert_finite, feature_set

MODEL_LABELS = {
    "A_clim": "A: climatology",
    "A2_clim_trend": "A2: climatology + trend",
    "B_anom": "B: anomaly logistic",
    "B2_anom_trend": "B2: anomaly + trend logistic",
}


class ClimatologyModel:
    """P(event) = share of past issue dates within ±halfwidth calendar days that saw the event.

    Uses a Jeffreys-style (k + 0.5) / (n + 1) estimate so probabilities never hit exactly 0 or 1.
    """

    def __init__(self, halfwidth: int = 7):
        self.halfwidth = halfwidth

    def fit(self, doy: np.ndarray, y: np.ndarray) -> "ClimatologyModel":
        doy, y = np.asarray(doy), np.asarray(y, float)
        ok = ~np.isnan(y)
        doy, y = doy[ok], y[ok]
        self.table_ = np.empty(365)
        for k in range(1, 366):
            dist = np.abs(doy - k)
            m = np.minimum(dist, 365 - dist) <= self.halfwidth
            self.table_[k - 1] = (y[m].sum() + 0.5) / (m.sum() + 1.0)
        return self

    def predict_proba(self, doy: np.ndarray) -> np.ndarray:
        return self.table_[np.asarray(doy) - 1]


class LogitModel:
    def __init__(self, features: list[str], C: float = 1.0):
        self.features = features
        self.pipe = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=1000))

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "LogitModel":
        Xv = X[self.features].to_numpy(float)
        assert_finite(Xv, "training features")
        self.pipe.fit(Xv, np.asarray(y).astype(int))
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        Xv = X[self.features].to_numpy(float)
        assert_finite(Xv, "forecast features")
        return self.pipe.predict_proba(Xv)[:, 1]

    def coefficients(self) -> pd.Series:
        lr = self.pipe[-1]
        return pd.Series(lr.coef_[0], index=self.features)


def make_logit(name: str, C: float) -> LogitModel:
    return LogitModel(feature_set({"A2_clim_trend": "season_trend", "B_anom": "anomaly",
                                   "B2_anom_trend": "anomaly_trend"}[name]), C=C)
