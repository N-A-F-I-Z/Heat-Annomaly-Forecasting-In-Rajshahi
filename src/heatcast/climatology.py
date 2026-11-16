"""Calendar-day climatology, hot-day thresholds and anomalies."""

from __future__ import annotations

import numpy as np
import pandas as pd


def doy365(index: pd.DatetimeIndex) -> np.ndarray:
    """Day of year on a 365-day calendar (Feb 29 shares Feb 28's index)."""
    doy = index.dayofyear.to_numpy().copy()
    leap_after = index.is_leap_year & (index.month > 2)
    doy[leap_after] -= 1
    doy[index.is_leap_year & (index.month == 2) & (index.day == 29)] = 59
    return doy


def _pooled_stat(series: pd.Series, base_start: int, base_end: int, halfwidth: int, fn) -> pd.Series:
    base = series[(series.index.year >= base_start) & (series.index.year <= base_end)]
    d = doy365(base.index)
    vals = base.to_numpy()
    out = np.empty(365)
    for k in range(1, 366):
        dist = np.abs(d - k)
        dist = np.minimum(dist, 365 - dist)  # circular
        out[k - 1] = fn(vals[dist <= halfwidth])
    return pd.Series(out, index=pd.RangeIndex(1, 366, name="doy"))


def doy_threshold(series: pd.Series, base_start: int, base_end: int, q: float = 0.9,
                  halfwidth: int = 7) -> pd.Series:
    """Calendar-day q-quantile of Tmax over the base period, pooled in a ±halfwidth window
    (the ETCCDI TX90p construction)."""
    return _pooled_stat(series, base_start, base_end, halfwidth, lambda v: np.quantile(v, q))


def doy_mean(series: pd.Series, base_start: int, base_end: int, halfwidth: int = 15) -> pd.Series:
    """Smoothed calendar-day mean Tmax over the base period."""
    return _pooled_stat(series, base_start, base_end, halfwidth, np.mean)


def lookup(by_doy: pd.Series, index: pd.DatetimeIndex) -> np.ndarray:
    return by_doy.to_numpy()[doy365(index) - 1]


def anomalies(series: pd.Series, clim_mean: pd.Series) -> pd.Series:
    return pd.Series(series.to_numpy() - lookup(clim_mean, series.index), index=series.index,
                     name="anom")


def hot_days(series: pd.Series, threshold: pd.Series) -> pd.Series:
    """1 where Tmax strictly exceeds the calendar-day threshold."""
    return pd.Series((series.to_numpy() > lookup(threshold, series.index)).astype(int),
                     index=series.index, name="hot")
