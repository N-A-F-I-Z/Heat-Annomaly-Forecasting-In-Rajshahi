"""Probabilistic forecast verification."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.metrics import roc_auc_score


def brier(p, y) -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    return float(np.mean((p - y) ** 2))


def brier_skill(p, y, p_ref) -> float:
    return 1.0 - brier(p, y) / brier(p_ref, y)


def log_loss(p, y, eps: float = 1e-6) -> float:
    p = np.clip(np.asarray(p, float), eps, 1 - eps)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def bin_edges(n_bins: int) -> np.ndarray:
    return np.linspace(0, 1, n_bins + 1)


def murphy_decomposition(p, y, n_bins: int = 10) -> dict:
    """BS ≈ reliability - resolution + uncertainty (exact when forecasts take bin-constant values)."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    idx = np.clip(np.digitize(p, bin_edges(n_bins)[1:-1]), 0, n_bins - 1)
    N, ybar = len(y), y.mean()
    rel = res = 0.0
    for k in range(n_bins):
        m = idx == k
        if m.any():
            nk, pk, ok = m.sum(), p[m].mean(), y[m].mean()
            rel += nk * (pk - ok) ** 2
            res += nk * (ok - ybar) ** 2
    return {"reliability": rel / N, "resolution": res / N, "uncertainty": ybar * (1 - ybar)}


def reliability_table(p, y, n_bins: int = 10) -> pd.DataFrame:
    """Per-bin mean forecast, observed frequency and a 95% Wilson interval."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    edges = bin_edges(n_bins)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    z = norm.ppf(0.975)
    rows = []
    for k in range(n_bins):
        m = idx == k
        n = int(m.sum())
        if n == 0:
            rows.append(dict(bin_lo=edges[k], bin_hi=edges[k + 1], n=0, p_mean=np.nan,
                             obs_freq=np.nan, lo=np.nan, hi=np.nan))
            continue
        o = y[m].mean()
        c = (o + z**2 / (2 * n)) / (1 + z**2 / n)
        h = z * np.sqrt(o * (1 - o) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
        rows.append(dict(bin_lo=edges[k], bin_hi=edges[k + 1], n=n, p_mean=p[m].mean(),
                         obs_freq=o, lo=c - h, hi=c + h))
    return pd.DataFrame(rows)


def sharpness(p, base_rate: float) -> dict:
    p = np.asarray(p, float)
    return {
        "p_std": float(p.std()),
        "mean_abs_dev_from_base": float(np.mean(np.abs(p - base_rate))),
        "share_confident": float(np.mean((p <= 0.1) | (p >= 0.6))),
    }


def block_bootstrap_idx(n: int, block_len: int, rng: np.random.Generator) -> np.ndarray:
    """Moving-block bootstrap indices (blocks of consecutive forecasts)."""
    n_blocks = int(np.ceil(n / block_len))
    starts = rng.integers(0, n - block_len + 1, size=n_blocks)
    return (starts[:, None] + np.arange(block_len)[None, :]).ravel()[:n]


def bootstrap_skill(p, y, p_ref, n_boot=2000, block_len=7, seed=42) -> dict:
    """BSS of p vs p_ref and Brier difference, with block-bootstrap 95% intervals."""
    p, y, p_ref = (np.asarray(a, float) for a in (p, y, p_ref))
    rng = np.random.default_rng(seed)
    bss, dbs = [], []
    for _ in range(n_boot):
        i = block_bootstrap_idx(len(y), block_len, rng)
        b, br = brier(p[i], y[i]), brier(p_ref[i], y[i])
        bss.append(1 - b / br if br > 0 else np.nan)
        dbs.append(br - b)
    bss, dbs = np.array(bss), np.array(dbs)
    return {
        "bss": brier_skill(p, y, p_ref),
        "bss_lo": float(np.nanpercentile(bss, 2.5)),
        "bss_hi": float(np.nanpercentile(bss, 97.5)),
        "p_better": float(np.mean(dbs > 0)),  # bootstrap share in which p beats the reference
    }


def summarize(pred: pd.DataFrame, models, ref: str = "A_clim", n_bins=10, n_boot=2000,
              block_len=7, seed=42) -> pd.DataFrame:
    pred = pred.sort_values("date")
    y = pred.y.to_numpy()
    base = y.mean()
    out = []
    for m in models:
        p = pred[m].to_numpy()
        d = murphy_decomposition(p, y, n_bins)
        row = {"model": m, "n": len(y), "base_rate": base, "brier": brier(p, y),
               "log_loss": log_loss(p, y),
               "auc": roc_auc_score(y, p) if 0 < y.sum() < len(y) else np.nan, **d,
               **sharpness(p, base)}
        if m == ref:
            row.update(bss=0.0, bss_lo=0.0, bss_hi=0.0, p_better=np.nan)
        else:
            row.update(bootstrap_skill(p, y, pred[ref].to_numpy(), n_boot, block_len, seed))
        out.append(row)
    return pd.DataFrame(out).set_index("model")
