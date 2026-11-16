"""The forecast target.

Event E(t): at least ``min_hot_days`` days in the window [t, t + horizon - 1] have
Tmax above the calendar-day 90th-percentile threshold. A forecast for E(t) is issued
at the start of day t and may use observations up to day t - latency.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def event_labels(hot: pd.Series, horizon: int = 7, min_hot_days: int = 2) -> pd.Series:
    """Label every day t with E(t); NaN where the window runs past the end of the data."""
    counts = hot.rolling(horizon).sum().shift(-(horizon - 1))  # sum over t..t+h-1
    y = (counts >= min_hot_days).astype(float)
    y[counts.isna()] = np.nan
    y.name = "event"
    return y


def issue_dates(years, season_start: str = "04-01", season_end: str = "05-31",
                horizon: int = 7) -> pd.DatetimeIndex:
    """Issue dates whose full forecast window lies inside the season, for each year."""
    out = []
    for y in years:
        first = pd.Timestamp(f"{y}-{season_start}")
        last = pd.Timestamp(f"{y}-{season_end}") - pd.Timedelta(days=horizon - 1)
        out.append(pd.date_range(first, last, freq="D"))
    return pd.DatetimeIndex(np.concatenate(out)) if out else pd.DatetimeIndex([])
