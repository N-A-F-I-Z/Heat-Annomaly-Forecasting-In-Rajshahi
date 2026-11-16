"""End-to-end experiment: hindcast, verification, figures, report."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import plots
from .data import data_source, load_series
from .hindcast import LOGIT_MODELS, prepare, run_hindcast
from .models import MODEL_LABELS
from .report import render_reports
from .verification import reliability_table, summarize

MODELS = ["A_clim", *LOGIT_MODELS]


def run(cfg: dict, out_dir: str | Path = "results", quick: bool = False) -> dict:
    out = Path(out_dir)
    fig_dir = out / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    vc = cfg["verification"]
    n_boot = 200 if quick else vc["n_boot"]
    vkw = dict(n_bins=vc["n_bins"], n_boot=n_boot, block_len=vc["block_len"], seed=vc["seed"])

    series = load_series(cfg["data"]["path"])
    source = data_source(cfg["data"]["path"])
    prep = prepare(series, cfg)
    print(f"Loaded {len(series)} days ({series.index.min().date()}..{series.index.max().date()}), source={source}")

    # 1. Primary hindcast (2021-2025)
    pred, fits = run_hindcast(prep, cfg, return_fits=True)
    pred.to_csv(out / "hindcast_predictions.csv", index=False)
    primary = summarize(pred, MODELS, **vkw)
    per_year = pd.DataFrame({
        Y: summarize(pred[pred.year == Y], MODELS, n_bins=vc["n_bins"], n_boot=50,
                     block_len=vc["block_len"], seed=vc["seed"])["brier"]
        for Y in sorted(pred.year.unique())}).T
    per_year["n_events"] = pred.groupby("year").y.sum()
    rel = {m: reliability_table(pred[m], pred.y, vc["n_bins"]) for m in MODELS}
    print("\nPrimary hindcast:\n", primary[["brier", "bss", "bss_lo", "bss_hi", "auc", "reliability", "resolution"]].round(3))

    # 2. Extended expanding-window hindcast (robustness)
    hc = cfg["hindcast"]
    ext_years = range(hc["extended_test_start"], hc["test_end"] + 1)
    pred_ext = run_hindcast(prep, cfg, test_years=ext_years)
    extended = summarize(pred_ext, MODELS, **vkw)
    pred_ext.to_csv(out / "hindcast_predictions_extended.csv", index=False)

    # 3. Latency sweep on the extended period (more data -> tighter intervals)
    sweep_rows = []
    for L in cfg["models"]["latency_sweep"]:
        pl = run_hindcast(prep, cfg, test_years=ext_years, latency=L,
                          models=("A_clim", "B_anom", "B2_anom_trend"))
        s = summarize(pl, ["A_clim", "B_anom", "B2_anom_trend"], **vkw)
        for m in ["B_anom", "B2_anom_trend"]:
            sweep_rows.append(dict(latency=L, model=m, bss=s.loc[m, "bss"], bss_lo=s.loc[m, "bss_lo"],
                                   bss_hi=s.loc[m, "bss_hi"], auc=s.loc[m, "auc"]))
    sweep = pd.DataFrame(sweep_rows)
    sweep.to_csv(out / "latency_sweep.csv", index=False)

    # 4. Figures
    final_year = max(pred.year)
    plots.threshold_plot(prep, cfg, fig_dir / "threshold_climatology.png")
    plots.event_frequency_plot(prep, cfg, fig_dir / "event_frequency_by_year.png")
    plots.reliability_plot(pred, ["A_clim", "B_anom"], vc["n_bins"], fig_dir / "reliability_A_vs_B.png")
    plots.reliability_plot(pred_ext, ["A_clim", "B_anom"], vc["n_bins"], fig_dir / "reliability_A_vs_B_extended.png")
    plots.timeseries_plot(pred, prep, ["A_clim", "B_anom"], fig_dir / "hindcast_timeseries.png")
    plots.latency_plot(sweep, fig_dir / "latency_sweep.png")
    plots.coefficient_plot(fits[(final_year, "B2_anom_trend")], fig_dir / "coefficients_B2.png")

    # 5. Metrics + reports
    thr_aprmay = prep.threshold.loc[91:151]
    metrics = {
        "source": source,
        "location": cfg["location"],
        "period": [str(series.index.min().date()), str(series.index.max().date())],
        "config": {"event": cfg["event"], "hindcast": cfg["hindcast"]},
        "threshold_aprmay_c": [float(thr_aprmay.min()), float(thr_aprmay.max())],
        "n_bootstrap": n_boot,
        "primary": json.loads(primary.to_json(orient="index")),
        "extended": json.loads(extended.to_json(orient="index")),
        "per_year_brier": json.loads(per_year.to_json(orient="index")),
        "latency_sweep": sweep.to_dict(orient="records"),
        "reliability_primary": {m: t.to_dict(orient="records") for m, t in rel.items()},
        "coefficients_B2_final": fits[(final_year, "B2_anom_trend")].coefficients().to_dict(),
        "coefficients_B_final": fits[(final_year, "B_anom")].coefficients().to_dict(),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float), encoding="utf-8")
    render_reports(metrics, primary, extended, per_year, sweep, out)
    return metrics
