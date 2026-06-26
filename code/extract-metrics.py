#!/usr/bin/env python3
"""Extract MRIQC fd_mean and tsnr values into a CSV table."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from pipeline_utils import read_subject_list


DEFAULT_TASKS = ("ugr", "doors", "socialdoors", "trust", "sharedreward")
DEFAULT_SESSIONS = ("01", "02")


def extract_metrics(mriqc_dir: Path, subjects: list[str], sessions: list[str], tasks: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for sub in subjects:
        for ses in sessions:
            for task in tasks:
                pattern = (
                    f"sub-{sub}/ses-{ses}/func/"
                    f"sub-{sub}_ses-{ses}_task-{task}_run-*_echo-2_part-mag_bold.json"
                )
                for json_file in sorted(mriqc_dir.glob(pattern)):
                    run = json_file.name.split("_run-")[-1].split("_")[0]
                    try:
                        data = json.loads(json_file.read_text())
                        tsnr = data.get("tsnr", "missing")
                        fd_mean = data.get("fd_mean", "missing")
                    except Exception as exc:  # noqa: BLE001 - batch extractor should report all bad files.
                        print(f"Error reading {json_file}: {exc}")
                        tsnr = "missing"
                        fd_mean = "missing"
                    rows.append(
                        {
                            "subject": sub,
                            "session": f"ses-{ses}",
                            "task": task,
                            "run": run,
                            "tsnr": str(tsnr),
                            "fd_mean": str(fd_mean),
                            "json_file": str(json_file),
                        }
                    )
    return rows


def write_csv(rows: list[dict[str, str]], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_file.with_name(f".{output_file.name}.tmp")
    fieldnames = ["subject", "session", "task", "run", "tsnr", "fd_mean", "json_file"]
    with tmp.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(output_file)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mriqc-dir", type=Path, default=repo_root / "derivatives" / "mriqc")
    parser.add_argument("--sublist", type=Path, default=repo_root / "code" / "sublist_all.txt")
    parser.add_argument("--output-file", type=Path, default=repo_root / "derivatives" / "mriqc-metrics.csv")
    parser.add_argument("--sessions", nargs="+", default=list(DEFAULT_SESSIONS))
    parser.add_argument("--tasks", nargs="+", default=list(DEFAULT_TASKS))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    subjects = read_subject_list(args.sublist)
    rows = extract_metrics(args.mriqc_dir, subjects, args.sessions, args.tasks)
    print(f"Found {len(rows)} MRIQC metric rows.")
    if args.dry_run:
        for row in rows[:10]:
            print(row)
        return 0
    write_csv(rows, args.output_file)
    print(f"Saved MRIQC metrics to: {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
