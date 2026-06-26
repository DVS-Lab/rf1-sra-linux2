#!/usr/bin/env python3
"""Generate FSL confound TSVs from fMRIPrep and TEDANA outputs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


DESIRED_FMRIPREP_COLUMNS = [
    "a_comp_cor_00",
    "a_comp_cor_01",
    "a_comp_cor_02",
    "a_comp_cor_03",
    "a_comp_cor_04",
    "a_comp_cor_05",
    "trans_x",
    "trans_y",
    "trans_z",
    "rot_x",
    "rot_y",
    "rot_z",
    "framewise_displacement",
]


def parse_metric_file(path: Path) -> dict[str, str]:
    match = re.search(
        r"/(?P<sub>sub-\d+)/ses-(?P<ses>\d+)/.*?_task-(?P<task>.*?)_run-(?P<run>.*?)_desc-tedana_metrics.tsv$",
        path.as_posix(),
    )
    if not match:
        raise ValueError(f"Could not parse TEDANA metric path: {path}")
    return match.groupdict()


def rejected_component_columns(metrics: pd.DataFrame) -> list[int]:
    rejected = metrics.loc[metrics["classification"] == "rejected", "Component"]
    indices: list[int] = []
    for component in rejected:
        value = str(component).replace("ICA_", "")
        indices.append(int(value))
    return indices


def build_confounds(fmriprep_confounds: Path, mixing_file: Path, metrics_file: Path) -> pd.DataFrame:
    fmriprep = pd.read_csv(fmriprep_confounds, sep="\t")
    mixing = pd.read_csv(mixing_file, sep="\t")
    metrics = pd.read_csv(metrics_file, sep="\t")

    cols = [c for c in DESIRED_FMRIPREP_COLUMNS if c in fmriprep.columns]
    cols.extend(c for c in fmriprep.columns if c.startswith("cosine"))
    cols.extend(c for c in fmriprep.columns if c.startswith("non_steady_state"))

    base = fmriprep[cols].fillna(0)
    rejected_indices = rejected_component_columns(metrics)
    rejected = mixing.iloc[:, rejected_indices] if rejected_indices else pd.DataFrame(index=mixing.index)

    if len(base) != len(rejected):
        raise ValueError(
            f"Row count mismatch: {fmriprep_confounds} has {len(base)} rows, "
            f"{mixing_file} has {len(rejected)} rows"
        )
    return pd.concat([base, rejected], axis=1)


def atomic_write_tsv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    df.to_csv(tmp, index=False, header=False, sep="\t")
    tmp.replace(path)


def main() -> int:
    repo_root = Path("/ZPOOL/data/projects/rf1-sra-linux2")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fmriprep-dir", type=Path, default=repo_root / "derivatives" / "fmriprep")
    parser.add_argument("--tedana-dir", type=Path, default=repo_root / "derivatives" / "tedana")
    parser.add_argument("--output-dir", type=Path, default=repo_root / "derivatives" / "fsl" / "confounds_tedana")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    metric_files = sorted(args.tedana_dir.rglob("*_desc-tedana_metrics.tsv"))
    failures = 0
    for metric_file in metric_files:
        parsed = parse_metric_file(metric_file)
        sub = parsed["sub"]
        ses = parsed["ses"]
        task = parsed["task"]
        run = parsed["run"]
        prefix = metric_file.name.replace("_desc-tedana_metrics.tsv", "")
        base = metric_file.parent / prefix
        mixing_file = base.with_name(f"{prefix}_desc-ICA_mixing.tsv")
        fmriprep_file = (
            args.fmriprep_dir
            / sub
            / f"ses-{ses}"
            / "func"
            / f"{sub}_ses-{ses}_task-{task}_run-{run}_part-mag_desc-confounds_timeseries.tsv"
        )
        out_file = (
            args.output_dir
            / sub
            / f"{sub}_ses-{ses}_task-{task}_run-{run}_desc-TedanaPlusConfounds.tsv"
        )

        missing = [p for p in [mixing_file, fmriprep_file] if not p.exists()]
        if missing:
            failures += 1
            print(f"Missing confound input for {sub} ses-{ses} task-{task} run-{run}:")
            for path in missing:
                print(f"  {path}")
            continue

        print(f"Making confounds: {sub} ses-{ses} task-{task} run-{run} -> {out_file}")
        if args.dry_run:
            continue
        try:
            confounds = build_confounds(fmriprep_file, mixing_file, metric_file)
            atomic_write_tsv(confounds, out_file)
        except Exception as exc:  # noqa: BLE001 - keep batch processing and report all failures.
            failures += 1
            print(f"Failed {sub} ses-{ses} task-{task} run-{run}: {exc}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
