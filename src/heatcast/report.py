"""Render the results report and the write-up from computed metrics.

The write-up (docs/writeup.md) is generated from docs/writeup_template.md, so every
number in it comes from the latest run. Re-running on real ERA5-Land data rewrites it.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

import pandas as pd

from .models import MODEL_LABELS

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "docs" / "writeup_template.md"


def _fmt(x, nd=3):
    return "–" if pd.isna(x) else f"{x:.{nd}f}"


def skill_table(df: pd.DataFrame) -> str:
    lines = ["| Model | Brier ↓ | BSS vs A ↑ (95% CI) | P(better than A) | Log loss ↓ | AUC ↑ | Reliability ↓ | Resolution ↑ | Sharpness (SD of p) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for m, r in df.iterrows():
        ci = "reference" if m == "A_clim" else f"{r.bss:+.3f} ({r.bss_lo:+.3f}, {r.bss_hi:+.3f})"
        pb = "–" if pd.isna(r.p_better) else f"{r.p_better:.0%}"
        lines.append(f"| {MODEL_LABELS[m]} | {_fmt(r.brier)} | {ci} | {pb} | {_fmt(r.log_loss)} | {_fmt(r.auc)} | "
                     f"{_fmt(r.reliability, 4)} | {_fmt(r.resolution, 4)} | {_fmt(r.p_std)} |")
    return "\n".join(lines)


def per_year_table(df: pd.DataFrame) -> str:
    cols = [c for c in MODEL_LABELS if c in df.columns]
    lines = ["| Year | Event days (of issue dates) | " + " | ".join(MODEL_LABELS[c].split(":")[0] for c in cols) + " |",
             "|---|---|" + "---|" * len(cols)]
    for Y, r in df.iterrows():
        best = min(cols, key=lambda c: r[c])
        cells = [f"**{r[c]:.3f}**" if c == best else f"{r[c]:.3f}" for c in cols]
        lines.append(f"| {Y} | {int(r.n_events)} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def latency_table(sweep: pd.DataFrame) -> str:
    w = sweep.pivot(index="latency", columns="model", values="bss")
    lines = ["| Latency (days) | " + " | ".join(MODEL_LABELS[c] for c in w.columns) + " |",
             "|---|" + "---|" * len(w.columns)]
    for L, r in w.iterrows():
        lines.append(f"| {L} | " + " | ".join(f"{v:+.3f}" for v in r) + " |")
    return "\n".join(lines)


def _verdict(r) -> str:
    if r.bss_lo > 0:
        return "a clear improvement on climatology (the 95% interval excludes zero)"
    if r.bss_hi < 0:
        return "worse than climatology (the 95% interval lies below zero)"
    if r.bss > 0:
        return "a positive but not statistically clear improvement (the 95% interval includes zero)"
    return "no improvement on climatology"


def narrative(primary: pd.DataFrame, extended: pd.DataFrame, sweep: pd.DataFrame, metrics: dict) -> dict:
    A, B, A2, B2 = (primary.loc[m] for m in ["A_clim", "B_anom", "A2_clim_trend", "B2_anom_trend"])
    eB, eA2 = extended.loc["B_anom"], extended.loc["A2_clim_trend"]
    sB = sweep[sweep.model == "B_anom"].set_index("latency")
    lat_pos = sB[sB.bss_lo > 0].index
    lat_txt = (f"Model B keeps a clear advantage (95% interval above zero) up to a latency of {int(lat_pos.max())} day{'s' if lat_pos.max() > 1 else ''}"
               if len(lat_pos) else "No latency gives Model B a clear advantage")
    best = primary.brier.idxmin()
    trend_vs_anom = ("most of Model B's skill comes from short-term persistence rather than the warming trend"
                     if B.bss > A2.bss else
                     "the warming trend alone (A2) does as well as or better than short-term anomalies (B)")
    return {
        "headline": (f"Over the {int(A.n)} April–May issue dates in "
                     f"{metrics['config']['hindcast']['test_start']}–{metrics['config']['hindcast']['test_end']}, "
                     f"the anomaly-adjusted model (B) scored a Brier score of {B.brier:.3f} against {A.brier:.3f} for "
                     f"climatology (A): a Brier skill score of {B.bss:+.2f} (95% block-bootstrap interval "
                     f"{B.bss_lo:+.2f} to {B.bss_hi:+.2f}). That is {_verdict(B)}."),
        "decomp": (f"In the Murphy decomposition, Model B's resolution is {B.resolution:.4f} against "
                   f"{A.resolution:.4f} for climatology (higher is better), and its reliability term is "
                   f"{B.reliability:.4f} against {A.reliability:.4f} (lower is better). Its ROC AUC is "
                   f"{B.auc:.2f} against {A.auc:.2f}, and its forecasts spread more widely around the base rate "
                   f"(SD {B.p_std:.2f} against {A.p_std:.2f}). "
                   + ("B is both sharper and better resolved: it separates hot weeks from ordinary ones "
                      "rather than just repeating the seasonal average."
                      if B.resolution > A.resolution and B.p_std > A.p_std else
                      "B is sharper, but that sharpness does not yet translate into better resolution.")
                   + (" The price is some loss of calibration (a larger reliability term): the resolution "
                      "gain outweighs it, but B's probabilities should not be read at face value without "
                      "checking the reliability diagram."
                      if B.reliability > A.reliability and B.resolution > A.resolution else "")),
        "ablation": (f"Adding a linear year term gives a BSS of {A2.bss:+.2f} for climatology (A2) and {B2.bss:+.2f} "
                     f"for the anomaly model (B2), against {B.bss:+.2f} for B without the trend. "
                     f"So {trend_vs_anom}. The best model by Brier score in the primary window is "
                     f"{MODEL_LABELS[best]}."),
        "extended": (f"The 2001–2025 expanding-window hindcast ({int(eB.n)} forecasts) gives "
                     f"a BSS of {eB.bss:+.2f} ({eB.bss_lo:+.2f} to {eB.bss_hi:+.2f}) for B, and "
                     f"{eA2.bss:+.2f} for the trend-only model A2."),
        "latency": (f"{lat_txt}. Its skill falls from {sB.bss.iloc[0]:+.2f} at {int(sB.index[0])}-day latency to "
                    f"{sB.bss.iloc[-1]:+.2f} at {int(sB.index[-1])} days."),
    }


def render_reports(metrics, primary, extended, per_year, sweep, out: Path):
    synthetic = metrics["source"] == "synthetic"
    banner = ("> **⚠ DEMO RUN ON SYNTHETIC DATA.** The numbers below come from a stochastic "
              "Rajshahi-like series generated by `heatcast fetch --source synthetic`. They test the "
              "pipeline; they are **not** findings about Rajshahi. Run the pipeline on ERA5-Land "
              "(`heatcast fetch --source gee`, then `heatcast run`) to regenerate this document with real results.\n"
              if synthetic else "")
    nar = narrative(primary, extended, sweep, metrics)
    lo, hi = metrics["threshold_aprmay_c"]
    subs = dict(
        banner=banner, source=metrics["source"],
        period=f"{metrics['period'][0]} to {metrics['period'][1]}",
        thr_lo=f"{lo:.1f}", thr_hi=f"{hi:.1f}",
        n_primary=int(primary.loc["A_clim", "n"]), n_extended=int(extended.loc["A_clim", "n"]),
        base_rate=f"{primary.loc['A_clim', 'base_rate']:.0%}",
        base_rate_ext=f"{extended.loc['A_clim', 'base_rate']:.0%}",
        n_boot=metrics["n_bootstrap"],
        table_primary=skill_table(primary), table_extended=skill_table(extended),
        table_per_year=per_year_table(per_year), table_latency=latency_table(sweep),
        **nar,
    )
    report = (f"# Results: {metrics['location']['name']} extreme-heat hindcast\n\n{banner}\n"
              f"Data: `{metrics['source']}`, {subs['period']}.\n\n"
              f"## Primary hindcast ({subs['n_primary']} forecasts, base rate {subs['base_rate']})\n\n"
              f"{subs['table_primary']}\n\n{nar['headline']}\n\n"
              f"## Brier score by test year\n\n{subs['table_per_year']}\n\n"
              f"## Extended hindcast 2001–2025 ({subs['n_extended']} forecasts)\n\n{subs['table_extended']}\n\n"
              f"## Latency sweep (extended period, BSS vs A)\n\n{subs['table_latency']}\n\n"
              "Figures are in `results/figures/`.\n")
    (out / "report.md").write_text(report, encoding="utf-8")
    if TEMPLATE.exists():
        import re
        src = re.sub(r"\A<!--.*?-->\s*", "", TEMPLATE.read_text(encoding="utf-8"), flags=re.S)
        text = Template(src).safe_substitute(subs)
        # only the canonical results/ run updates docs/writeup.md; other output dirs get their own copy
        dest = ROOT / "docs" / "writeup.md" if out.resolve() == (ROOT / "results").resolve() else out / "writeup.md"
        dest.write_text(text, encoding="utf-8")
        print(f"Wrote {out / 'report.md'} and {dest}")
