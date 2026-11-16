"""Forecasts issued on day t must not depend on observations from day t - latency + 1 onward.

We corrupt every observation from a cutoff date onward (temperatures +15 °C) and check
that forecasts issued on or before the cutoff are bit-for-bit identical. Thresholds come
from the fixed 1991-2020 base period, so they are unaffected by the corruption.
"""

import numpy as np
import pandas as pd
import pytest

from heatcast.hindcast import prepare, run_hindcast

MODELS = ["A_clim", "A2_clim_trend", "B_anom", "B2_anom_trend"]


@pytest.mark.parametrize("latency", [1, 5])
def test_no_lookahead(series, cfg, latency):
    cutoff = pd.Timestamp("2022-05-01")
    corrupted = series.copy()
    # the newest observation usable on `cutoff` is cutoff - latency; corrupt everything after it
    corrupted[corrupted.index > cutoff - pd.Timedelta(days=latency)] += 15.0

    p_clean = run_hindcast(prepare(series, cfg), cfg, test_years=[2022], latency=latency)
    p_bad = run_hindcast(prepare(corrupted, cfg), cfg, test_years=[2022], latency=latency)

    before = p_clean.date <= cutoff
    for m in MODELS:
        np.testing.assert_array_equal(p_clean.loc[before, m].to_numpy(), p_bad.loc[before, m].to_numpy())
    # sanity: the corruption does change later forecasts of the anomaly models
    after = p_clean.date > cutoff + pd.Timedelta(days=2)
    assert not np.allclose(p_clean.loc[after, "B_anom"], p_bad.loc[after, "B_anom"])


def test_training_uses_only_past_years(series, cfg):
    """Corrupting the test year itself must not change that year's forecasts' training fit,
    i.e. forecasts on the first issue date (whose features predate the season) stay equal."""
    corrupted = series.copy()
    corrupted["2022-04-01":] += 15.0
    a = run_hindcast(prepare(series, cfg), cfg, test_years=[2022])
    b = run_hindcast(prepare(corrupted, cfg), cfg, test_years=[2022])
    first = a.date == a.date.min()
    for m in MODELS:
        assert a.loc[first, m].iloc[0] == b.loc[first, m].iloc[0]
