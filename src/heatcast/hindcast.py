"""Expanding-window hindcast.

For each test year Y, every model is trained only on issue dates in years < Y and then
issues forecasts for every issue date in Y. Thresholds and the anomaly climatology come
from the fixed base period (1991-2020 by default), which ends before the first test year.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .climatology import anomalies, doy365, doy_mean, doy_threshold, hot_days
from .events import event_labels, issue_dates
from .features import build_features
from .models import ClimatologyModel, make_logit

LOGIT_MODELS = ["A2_clim_trend", "B_anom", "B2_anom_trend"]


@dataclass
class Prepared:
    series: pd.Series
    threshold: pd.Series
    clim_mean: pd.Series
    anom: pd.Series
    hot: pd.Series
    labels: pd.Series


def prepare(series: pd.Series, cfg: dict) -> Prepared:
    ev = cfg["event"]
    thr = doy_threshold(series, ev["base_start"], ev["base_end"], ev["quantile"], ev["window_halfwidth"])
    cm = doy_mean(series, ev["base_start"], ev["base_end"])
    anom = anomalies(series, cm)
    hot = hot_days(series, thr)
    labels = event_labels(hot, ev["horizon_days"], ev["min_hot_days"])
    return Prepared(series, thr, cm, anom, hot, labels)


def run_hindcast(prep: Prepared, cfg: dict, test_years=None, latency: int | None = None,
                 models=("A_clim", *LOGIT_MODELS), return_fits: bool = False):
    ev, hc, mc = cfg["event"], cfg["hindcast"], cfg["models"]
    latency = hc["data_latency_days"] if latency is None else latency
    if test_years is None:
        test_years = range(hc["test_start"], hc["test_end"] + 1)
    test_years = list(test_years)

    # Model A pools issue dates across the calendar, so it is trained on all days with a label.
    all_days = prep.labels.dropna()
    seas = dict(season_start=ev["season_start"], season_end=ev["season_end"], horizon=ev["horizon_days"])
    years_needed = sorted(set(range(hc["train_start"], max(test_years))) | set(test_years))
    feats = build_features(prep.anom, prep.hot, issue_dates(years_needed, **seas), latency)
    feats["y"] = prep.labels.reindex(feats.index).to_numpy()
    feats = feats.dropna(subset=["anom_7"])  # first days of the record have no history

    rows, fits = [], {}
    for Y in test_years:
        tr = feats[(feats.year >= hc["train_start"]) & (feats.year < Y)].dropna(subset=["y"])
        te = feats[feats.year == Y].dropna(subset=["y"])
        if len(te) == 0:
            continue
        out = pd.DataFrame({"date": te.index, "year": Y, "y": te.y.to_numpy().astype(int)})
        if "A_clim" in models:
            a_days = all_days[(all_days.index.year >= hc["train_start"]) & (all_days.index.year < Y)]
            mA = ClimatologyModel(mc["clim_window_halfwidth"]).fit(doy365(a_days.index), a_days.to_numpy())
            out["A_clim"] = mA.predict_proba(te.doy.to_numpy())
            fits[(Y, "A_clim")] = mA
        for name in LOGIT_MODELS:
            if name in models:
                m = make_logit(name, mc["logit_C"]).fit(tr, tr.y.to_numpy())
                out[name] = m.predict_proba(te)
                fits[(Y, name)] = m
        rows.append(out)
    pred = pd.concat(rows, ignore_index=True)
    return (pred, fits) if return_fits else pred
