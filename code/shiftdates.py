#!/usr/bin/env python3
"""Shift BIDS scans.tsv acquisition dates for de-identification."""

from __future__ import annotations

import argparse
import calendar
import csv
from datetime import datetime
from pathlib import Path


TSVRows = list[dict[str, str]]


def parse_acq_time(value: str) -> datetime:
    value = value.strip()
    if not value:
        raise ValueError("empty acq_time value")
    return datetime.fromisoformat(value)


def shift_months(value: datetime, months: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def read_tsv(path: Path) -> tuple[list[str], TSVRows]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def shift_scans_tsv(path: Path, months: int = 1200, operator: str = "tubric") -> TSVRows:
    fieldnames, rows = read_tsv(path)
    if "acq_time" not in fieldnames:
        raise ValueError(f"acq_time column not found in {path}")
    for row in rows:
        row["acq_time"] = shift_months(parse_acq_time(row["acq_time"]), months).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )
        row["operator"] = operator
    return rows


def atomic_write_tsv(rows: TSVRows, path: Path) -> None:
    fieldnames, _ = read_tsv(path)
    if "operator" not in fieldnames:
        fieldnames.append("operator")
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def preview_rows(rows: TSVRows, limit: int = 5) -> str:
    rows = rows[:limit]
    if not rows:
        return ""
    fieldnames = list(rows[0])
    lines = ["\t".join(fieldnames)]
    lines.extend("\t".join(row.get(field, "") for field in fieldnames) for row in rows)
    return "\n".join(lines)


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
        print(preview_rows(shifted))
        return 0
    atomic_write_tsv(shifted, args.scans_tsv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
