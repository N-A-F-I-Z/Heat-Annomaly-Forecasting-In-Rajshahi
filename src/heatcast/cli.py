"""Command-line interface.

    heatcast fetch [--source gee|openmeteo|synthetic]   download the daily Tmax series
    heatcast run   [--quick]                             hindcast + verification + figures + reports
    heatcast all   [--source ...]                        fetch then run
"""

from __future__ import annotations

import argparse

from .config import load_config


def main(argv=None):
    ap = argparse.ArgumentParser(prog="heatcast", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["fetch", "run", "all"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--source", choices=["gee", "openmeteo", "synthetic"], default=None)
    ap.add_argument("--data", default=None, help="override path to the daily CSV")
    ap.add_argument("--out", default="results")
    ap.add_argument("--quick", action="store_true", help="fewer bootstrap draws (for CI/smoke tests)")
    a = ap.parse_args(argv)

    cfg = load_config(a.config)
    if a.source:
        cfg["data"]["source"] = a.source
    if a.data:
        cfg["data"]["path"] = a.data

    if a.command in ("fetch", "all"):
        from .data import fetch
        fetch(cfg)
    if a.command in ("run", "all"):
        from .pipeline import run
        run(cfg, a.out, quick=a.quick)


if __name__ == "__main__":
    main()
