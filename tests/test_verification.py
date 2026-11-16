import numpy as np
import pytest

from heatcast.models import ClimatologyModel
from heatcast.verification import (bootstrap_skill, brier, brier_skill, murphy_decomposition,
                                   reliability_table)


def test_perfect_and_constant_forecasts():
    y = np.array([0, 1, 1, 0, 1])
    assert brier(y, y) == 0
    p = np.full(5, y.mean())
    assert brier_skill(p, y, p) == 0
    assert brier(p, y) == pytest.approx(y.mean() * (1 - y.mean()))


def test_murphy_decomposition_identity_for_binned_forecasts():
    rng = np.random.default_rng(0)
    # forecasts placed at bin centres so the decomposition is exact
    p = rng.choice(np.linspace(0.05, 0.95, 10), size=5000)
    y = (rng.random(5000) < p * 0.8 + 0.05).astype(float)
    d = murphy_decomposition(p, y, n_bins=10)
    assert d["reliability"] - d["resolution"] + d["uncertainty"] == pytest.approx(brier(p, y), abs=1e-12)


def test_reliability_of_calibrated_forecasts():
    rng = np.random.default_rng(1)
    p = rng.random(20000)
    y = (rng.random(20000) < p).astype(float)
    t = reliability_table(p, y, 10)
    assert np.all(np.abs(t.p_mean - t.obs_freq) < 0.03)
    assert np.all((t.lo <= t.obs_freq) & (t.obs_freq <= t.hi))


def test_bootstrap_detects_clearly_better_forecast():
    rng = np.random.default_rng(2)
    truth = rng.random(1000)
    y = (rng.random(1000) < truth).astype(float)
    r = bootstrap_skill(truth, y, np.full(1000, y.mean()), n_boot=300, block_len=7, seed=0)
    assert r["bss"] > 0 and r["bss_lo"] > 0 and r["p_better"] > 0.95


def test_climatology_model_frequencies():
    doy = np.tile(np.arange(1, 366), 10)
    y = (doy > 180).astype(float)
    m = ClimatologyModel(halfwidth=3).fit(doy, y)
    assert m.predict_proba(np.array([100]))[0] < 0.1
    assert m.predict_proba(np.array([300]))[0] > 0.9
