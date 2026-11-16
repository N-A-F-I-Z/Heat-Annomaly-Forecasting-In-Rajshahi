"""Data acquisition: ERA5-Land daily Tmax for a point.

Three sources share one output format: a CSV with columns ``date`` (YYYY-MM-DD) and
``tmax_c`` (daily maximum 2 m air temperature, °C).

* ``gee``       – Google Earth Engine, ``ECMWF/ERA5_LAND/DAILY_AGGR`` band ``temperature_2m_max``
                  (the dataset specified for this study; days are UTC days).
* ``openmeteo`` – Open-Meteo historical API with ``models=era5_land`` (same reanalysis,
                  no account needed; days are local Asia/Dhaka days).
* ``synthetic`` – a stochastic Rajshahi-like series for tests and demos. NOT real data.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

GEE_COLLECTION = "ECMWF/ERA5_LAND/DAILY_AGGR"
GEE_BAND = "temperature_2m_max"
ERA5_LAND_SCALE_M = 11132  # native ~0.1° grid


# --------------------------------------------------------------------------- GEE
def fetch_gee(lat: float, lon: float, start: str, end: str, buffer_m: float = 0,
              project: str | None = None) -> pd.DataFrame:
    """Download daily Tmax from Earth Engine, one year per request to stay under limits."""
    import ee  # imported lazily so the rest of the package works without it

    project = project or os.environ.get("EE_PROJECT") or None
    try:
        ee.Initialize(project=project)
    except Exception:  # first run on a machine: interactive auth
        ee.Authenticate()
        ee.Initialize(project=project)

    geom = ee.Geometry.Point([lon, lat])
    if buffer_m > 0:
        geom = geom.buffer(buffer_m)

    def to_feature(img):
        val = img.select(GEE_BAND).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom, scale=ERA5_LAND_SCALE_M
        ).get(GEE_BAND)
        return ee.Feature(None, {"date": img.date().format("YYYY-MM-dd"), "tmax_k": val})

    frames = []
    end_excl = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    for year in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1):
        y0 = max(pd.Timestamp(start), pd.Timestamp(f"{year}-01-01")).strftime("%Y-%m-%d")
        y1 = min(pd.Timestamp(end_excl), pd.Timestamp(f"{year + 1}-01-01")).strftime("%Y-%m-%d")
        fc = ee.FeatureCollection(
            ee.ImageCollection(GEE_COLLECTION).filterDate(y0, y1).select(GEE_BAND).map(to_feature)
        )
        info = fc.reduceColumns(ee.Reducer.toList(2), ["date", "tmax_k"]).get("list").getInfo()
        frames.append(pd.DataFrame(info, columns=["date", "tmax_k"]))
        print(f"  GEE {year}: {len(info)} days")

    df = pd.concat(frames, ignore_index=True)
    df["tmax_c"] = df.pop("tmax_k").astype(float) - 273.15
    return df


# ---------------------------------------------------------------------- Open-Meteo
def fetch_openmeteo(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    import requests

    r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params=dict(latitude=lat, longitude=lon, start_date=start, end_date=end,
                    daily="temperature_2m_max", models="era5_land", timezone="Asia/Dhaka"),
        timeout=120,
    )
    r.raise_for_status()
    d = r.json()["daily"]
    return pd.DataFrame({"date": d["time"], "tmax_c": d["temperature_2m_max"]})


# ----------------------------------------------------------------------- synthetic
def make_synthetic(start: str, end: str, seed: int = 0) -> pd.DataFrame:
    """Rajshahi-like Tmax: seasonal cycle + warming trend + AR(1) anomalies + heat spells.

    Seasonal cycle is tuned to a pre-monsoon peak (~36 °C in late April/May), a damped
    monsoon plateau (~32 °C) and a ~24 °C winter. Anomaly variance is largest in the
    pre-monsoon season. Intended only for tests and for demonstrating the pipeline.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq="D")
    doy = dates.dayofyear.to_numpy()
    w = 2 * np.pi * doy / 365.25
    clim = 30.8 - 3.9 * np.cos(w) + 2.4 * np.sin(w) - 1.2 * np.cos(2 * w) + 1.4 * np.sin(2 * w)
    sd = 1.1 + 1.3 * np.exp(-0.5 * ((doy - 120) / 28) ** 2)  # extra variance Apr-May
    years = dates.year.to_numpy() + doy / 365.25
    trend = 0.025 * (years - 2008)

    z = np.empty(len(dates))
    z[0] = 0.0
    eps = rng.standard_normal(len(dates))
    for i in range(1, len(dates)):
        z[i] = 0.72 * z[i - 1] + np.sqrt(1 - 0.72**2) * eps[i]

    spell = np.zeros(len(dates))  # occasional multi-day heat spells in the pre-monsoon
    for i in np.flatnonzero((doy > 85) & (doy < 160) & (rng.random(len(dates)) < 0.012)):
        L = rng.integers(3, 9)
        spell[i:i + L] += rng.uniform(1.5, 3.5) * np.hanning(L + 2)[1:-1]

    tmax = clim + trend + sd * z + spell
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "tmax_c": np.round(tmax, 2)})


# ---------------------------------------------------------------------------- I/O
def fetch(cfg: dict) -> Path:
    loc, dc = cfg["location"], cfg["data"]
    src = dc["source"]
    print(f"Fetching {src} Tmax for {loc['name']} ({loc['lat']}, {loc['lon']}) {dc['start']}..{dc['end']}")
    if src == "gee":
        df = fetch_gee(loc["lat"], loc["lon"], dc["start"], dc["end"], loc.get("buffer_m", 0),
                       dc.get("gee_project") or None)
    elif src == "openmeteo":
        df = fetch_openmeteo(loc["lat"], loc["lon"], dc["start"], dc["end"])
    elif src == "synthetic":
        df = make_synthetic(dc["start"], dc["end"], seed=cfg["verification"]["seed"])
    else:
        raise ValueError(f"unknown data source {src!r}")
    path = Path(dc["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    meta = path.with_suffix(".source.txt")
    meta.write_text(f"{src}\n", encoding="utf-8")
    print(f"Wrote {len(df)} rows to {path}")
    return path


def load_series(path: str | Path) -> pd.Series:
    """Load and validate the daily series; returns a float Series indexed by date."""
    df = pd.read_csv(path, parse_dates=["date"])
    s = df.set_index("date")["tmax_c"].astype(float).sort_index()
    s = s[~s.index.duplicated()]
    full = pd.date_range(s.index.min(), s.index.max(), freq="D")
    missing = full.difference(s.index)
    if len(missing):
        print(f"warning: {len(missing)} missing days; linearly interpolating gaps <= 3 days")
    s = s.reindex(full).interpolate(limit=3)
    if s.isna().any():
        raise ValueError(f"{int(s.isna().sum())} days still missing after gap filling")
    if not (5 < s.mean() < 45):
        raise ValueError(f"implausible mean Tmax {s.mean():.1f} °C; check units (expected °C)")
    s.name = "tmax_c"
    return s


def data_source(path: str | Path) -> str:
    meta = Path(path).with_suffix(".source.txt")
    return meta.read_text(encoding="utf-8").strip() if meta.exists() else "unknown"
