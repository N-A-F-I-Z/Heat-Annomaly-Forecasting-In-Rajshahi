import numpy as np
import pandas as pd
import pytest

from heatcast.climatology import doy365, doy_threshold
from heatcast.config import validate_config, load_config
from heatcast.events import event_labels, issue_dates


def test_event_counts_window_t_to_t_plus_6():
    idx = pd.date_range("2020-04-01", periods=14)
    hot = pd.Series([0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0], index=idx)
    y = event_labels(hot, horizon=7, min_hot_days=2)
    # window starting Apr 1 covers Apr 1..7 -> one hot day -> no event
    assert y.iloc[0] == 0
    # window starting Apr 2 covers Apr 2..8 -> two hot days -> event
    assert y.iloc[1] == 1
    assert y.iloc[7] == 0  # Apr 8..14 has one hot day
    assert y.iloc[-6:].isna().all()  # windows past the data end are undefined


def test_issue_dates_keep_window_in_season():
    d = issue_dates([2023], "04-01", "05-31", horizon=7)
    assert d[0] == pd.Timestamp("2023-04-01") and d[-1] == pd.Timestamp("2023-05-25")
    assert len(d) == 55


def test_doy365_leap_year():
    idx = pd.DatetimeIndex(["2020-02-28", "2020-02-29", "2020-03-01", "2021-03-01", "2020-12-31"])
    assert list(doy365(idx)) == [59, 59, 60, 60, 365]


def test_threshold_is_90th_percentile(series):
    thr = doy_threshold(series, 1991, 2020, 0.9, 7)
    assert thr.shape == (365,)
    base = series["1991":"2020"]
    frac_hot = (base.to_numpy() > thr.to_numpy()[doy365(base.index) - 1]).mean()
    assert 0.08 < frac_hot < 0.12


def test_config_rejects_base_period_overlapping_test():
    cfg = load_config()
    cfg["event"]["base_end"] = 2022
    with pytest.raises(ValueError):
        validate_config(cfg)


def test_hindcast_has_one_forecast_per_issue_date(series, cfg):
    from heatcast.hindcast import prepare, run_hindcast
    p = run_hindcast(prepare(series, cfg), cfg, test_years=[2021, 2022])
    assert len(p) == 2 * 55 and not p.date.duplicated().any()
