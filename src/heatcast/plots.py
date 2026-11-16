"""Figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .climatology import doy365
from .models import MODEL_LABELS
from .verification import reliability_table

COLORS = {"A_clim": "#7a7a7a", "A2_clim_trend": "#b8a06b", "B_anom": "#c0392b", "B2_anom_trend": "#2e6f9e"}
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 10})


def _save(fig, path: Path):
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def threshold_plot(prep, cfg, path: Path):
    ev = cfg["event"]
    s = prep.series
    base = s[(s.index.year >= ev["base_start"]) & (s.index.year <= ev["base_end"])]
    d = doy365(base.index)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.scatter(d, base.to_numpy(), s=1, alpha=0.08, color="k", label=f"daily Tmax {ev['base_start']}–{ev['base_end']}")
    x = np.arange(1, 366)
    ax.plot(x, prep.clim_mean.to_numpy(), color="#2e6f9e", lw=1.8, label="calendar-day mean")
    ax.plot(x, prep.threshold.to_numpy(), color="#c0392b", lw=1.8, label=f"{int(ev['quantile']*100)}th percentile threshold")
    ax.axvspan(91, 151, color="#f3c623", alpha=0.18, label="forecast season (Apr–May)")
    ax.set(xlabel="day of year", ylabel="Tmax (°C)", title=f"{cfg['location']['name']}: daily maximum temperature climatology")
    ax.legend(loc="lower center", fontsize=8, ncol=2)
    _save(fig, path)


def event_frequency_plot(prep, cfg, path: Path):
    from .events import issue_dates
    ev = cfg["event"]
    years = sorted(set(prep.series.index.year))
    dates = issue_dates(years, ev["season_start"], ev["season_end"], ev["horizon_days"])
    y = prep.labels.reindex(dates).dropna()
    freq = y.groupby(y.index.year).mean()
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.bar(freq.index, freq.to_numpy(), color=["#c0392b" if yr >= cfg["hindcast"]["test_start"] else "#9aa5ad" for yr in freq.index])
    z = np.polyfit(freq.index, freq.to_numpy(), 1)
    ax.plot(freq.index, np.polyval(z, freq.index), "k--", lw=1, label=f"linear trend {z[0]*10:+.2f} per decade")
    ax.set(ylabel="share of Apr–May issue dates\nwith event", title="How often the event happens each year (red = test years)")
    ax.legend(fontsize=8)
    _save(fig, path)


def reliability_plot(pred, models, n_bins, path: Path):
    fig = plt.figure(figsize=(9, 5.2))
    gs = fig.add_gridspec(2, len(models), height_ratios=[3, 1.1])
    for j, m in enumerate(models):
        ax = fig.add_subplot(gs[0, j])
        t = reliability_table(pred[m], pred.y, n_bins)
        t = t[t.n > 0]
        ax.plot([0, 1], [0, 1], color="k", lw=0.8, ls=":")
        ax.axhline(pred.y.mean(), color="k", lw=0.6, ls="--", alpha=0.5)
        ax.errorbar(t.p_mean, t.obs_freq, yerr=[t.obs_freq - t.lo, t.hi - t.obs_freq], fmt="o-",
                    color=COLORS[m], ms=4, capsize=2)
        for _, r in t.iterrows():
            ax.annotate(str(int(r.n)), (r.p_mean, r.obs_freq), textcoords="offset points", xytext=(4, -9), fontsize=6.5, color="#555")
        ax.set(xlim=(0, 1), ylim=(0, 1), title=MODEL_LABELS[m], xlabel="forecast probability")
        if j == 0:
            ax.set_ylabel("observed frequency")
        axh = fig.add_subplot(gs[1, j])
        axh.hist(pred[m], bins=np.linspace(0, 1, n_bins + 1), color=COLORS[m], alpha=0.8)
        axh.set(xlim=(0, 1), xlabel="forecast probability")
        if j == 0:
            axh.set_ylabel("count (sharpness)")
    fig.suptitle("Reliability diagrams (95% Wilson intervals, n per bin) with sharpness histograms", fontsize=10)
    _save(fig, path)


def timeseries_plot(pred, prep, models, path: Path):
    years = sorted(pred.year.unique())
    fig, axes = plt.subplots(len(years), 1, figsize=(9, 1.9 * len(years)), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, Y in zip(axes, years):
        d = pred[pred.year == Y].sort_values("date")
        hot = prep.hot[f"{Y}-04-01":f"{Y}-05-31"]
        for t in hot.index[hot.to_numpy() == 1]:
            ax.axvspan(t, t + pd.Timedelta(days=1), color="#f3c623", alpha=0.45, lw=0)
        ax.fill_between(d.date, 0, d.y, step="post", color="#c0392b", alpha=0.10, lw=0)
        for m in models:
            ax.plot(d.date, d[m], color=COLORS[m], lw=1.4, label=MODEL_LABELS[m])
        ax.set(ylim=(0, 1), ylabel=str(Y))
    axes[0].legend(fontsize=7, ncol=len(models), loc="upper left")
    axes[0].set_title("Hindcast probabilities. Yellow = hot day; pink = issue dates where the event occurred", fontsize=9)
    _save(fig, path)


def latency_plot(sweep: pd.DataFrame, path: Path):
    fig, ax = plt.subplots(figsize=(6, 3.4))
    for m in [c for c in ["B_anom", "B2_anom_trend"] if c in sweep.model.unique()]:
        s = sweep[sweep.model == m]
        ax.plot(s.latency, s.bss, "o-", color=COLORS[m], label=MODEL_LABELS[m])
        ax.fill_between(s.latency, s.bss_lo, s.bss_hi, color=COLORS[m], alpha=0.15)
    ax.axhline(0, color="k", lw=0.8)
    ax.set(xlabel="data latency (days between newest observation and issue date)",
           ylabel="Brier skill score vs A", title="How fast does the anomaly signal decay?")
    ax.legend(fontsize=8)
    _save(fig, path)


def coefficient_plot(model, path: Path):
    c = model.coefficients().sort_values()
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.barh(c.index, c.to_numpy(), color=["#c0392b" if v > 0 else "#2e6f9e" for v in c])
    ax.axvline(0, color="k", lw=0.8)
    ax.set(xlabel="standardised logistic coefficient (log-odds per SD)", title="Model B2 coefficients (final training fit)")
    _save(fig, path)
