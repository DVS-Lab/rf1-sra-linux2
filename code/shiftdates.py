#!/usr/bin/env python3
"""Shift BIDS scans.tsv acquisition dates for de-identification."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_acq_times(values: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(values, format="mixed")
    except (TypeError, ValueError):
        return values.map(lambda value: pd.to_datetime(value) if pd.notna(value) else pd.NaT)


def shift_scans_tsv(path: Path, months: int = 1200, operator: str = "tubric") -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    if "acq_time" not in df.columns:
        raise ValueError(f"acq_time column not found in {path}")
    df["acq_time"] = parse_acq_times(df["acq_time"])
    df["acq_time"] = df["acq_time"] - pd.DateOffset(months=months)
    df["acq_time"] = df["acq_time"].dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
    df["operator"] = operator
    return df


def atomic_write_tsv(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    df.to_csv(tmp, sep="\t", index=False)
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scans_tsv", type=Path)
    parser.add_argument("--months", type=int, default=1200)
    parser.add_argument("--operator", default="tubric")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"Scrubbing {args.scans_tsv}")
    shifted = shift_scans_tsv(args.scans_tsv, months=args.months, operator=args.operator)
    if args.dry_run:
        print(shifted.head().to_string(index=False))
        return 0
    atomic_write_tsv(shifted, args.scans_tsv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
