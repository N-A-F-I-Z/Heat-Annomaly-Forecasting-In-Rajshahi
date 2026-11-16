"""Predictors available at issue time.

Every feature for issue date t is built only from observations on days <= t - latency,
so a forecast never sees the window it is predicting. ``tests/test_leakage.py`` checks
this by corrupting future data and confirming the forecasts do not change.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .climatology import doy365

SEASON_FEATURES = ["season", "season2"]
ANOM_FEATURES = ["anom_1", "anom_3", "anom_7", "hot_7", "anom_tend"]
TREND_FEATURES = ["year_c"]


def build_features(anom: pd.Series, hot: pd.Series, dates: pd.DatetimeIndex,
                   latency: int = 1) -> pd.DataFrame:
    """Feature table indexed by issue date.

    anom_1    anomaly on the newest available day (t - latency)
    anom_3    mean anomaly over the newest 3 available days
    anom_7    mean anomaly over the newest 7 available days
    hot_7     number of hot days among the newest 7 available days
    anom_tend anom_3 - anom_7 (is the recent anomaly strengthening or fading?)
    season    position in the April-May season, scaled to [-1, 1]; season2 = season**2
    year_c    (year - 2008) / 10, a linear warming-trend term
    """
    if latency < 1:
        raise ValueError("latency must be >= 1")
    # value at t of x.shift(latency) is x[t - latency]
    a = anom.shift(latency)
    h = hot.shift(latency)
    f = pd.DataFrame(index=anom.index)
    f["anom_1"] = a
    f["anom_3"] = a.rolling(3).mean()
    f["anom_7"] = a.rolling(7).mean()
    f["hot_7"] = h.rolling(7).sum()
    f["anom_tend"] = f["anom_3"] - f["anom_7"]
    f = f.reindex(dates)

    d = doy365(dates)
    f["season"] = (d - 121.0) / 30.0  # 0 at ~May 1; ±1 near season edges
    f["season2"] = f["season"] ** 2
    f["year_c"] = (dates.year.to_numpy() - 2008) / 10.0
    f["doy"] = d
    f["year"] = dates.year.to_numpy()
    return f


def feature_set(name: str) -> list[str]:
    return {
        "season_trend": SEASON_FEATURES + TREND_FEATURES,
        "anomaly": SEASON_FEATURES + ANOM_FEATURES,
        "anomaly_trend": SEASON_FEATURES + ANOM_FEATURES + TREND_FEATURES,
    }[name]


def assert_finite(X: np.ndarray, what: str) -> None:
    if not np.isfinite(X).all():
        raise ValueError(f"non-finite values in {what}; is there enough data before the first issue date?")
