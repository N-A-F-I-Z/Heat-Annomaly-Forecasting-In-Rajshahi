"""Configuration loading."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config.toml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else DEFAULT_CONFIG
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict[str, Any]) -> None:
    ev, hc = cfg["event"], cfg["hindcast"]
    if ev["base_end"] >= hc["test_start"]:
        raise ValueError(
            "Base period for the threshold must end before the first test year "
            f"(base_end={ev['base_end']}, test_start={hc['test_start']}); otherwise the event "
            "definition itself uses test-period data."
        )
    if hc["data_latency_days"] < 1:
        raise ValueError("data_latency_days must be >= 1 (a forecast cannot use same-day data).")
    if not 1 <= ev["min_hot_days"] <= ev["horizon_days"]:
        raise ValueError("min_hot_days must be between 1 and horizon_days.")
