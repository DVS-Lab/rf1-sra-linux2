#!/usr/bin/env python3
"""Generate FSL confound TSVs from fMRIPrep and TEDANA outputs."""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline_utils import apply_umask_mode, read_subject_list


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


def atomic_write_tsv(df: pd.DataFrame, path: Path, *, preserve_existing: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        tmp = Path(handle.name)
    try:
        df.to_csv(tmp, index=False, header=False, sep="\t")
        apply_umask_mode(tmp)
        if preserve_existing:
            # Exclusive publication: a concurrent writer cannot be overwritten.
            os.link(tmp, path)
        else:
            tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def validate_alignment(confounds: pd.DataFrame, bold_file: Path) -> None:
    import nibabel as nib

    shape = nib.load(bold_file).shape
    if len(shape) != 4 or shape[3] != len(confounds):
        raise ValueError(f"BOLD/confound row mismatch: image shape {shape}, rows {len(confounds)}")
    values = confounds.to_numpy(dtype=float)
    if not values.size or not np.isfinite(values).all():
        raise ValueError("Confound matrix is empty or contains nonfinite values")


def verify_existing(confounds: pd.DataFrame, path: Path) -> None:
    actual = pd.read_csv(path, sep="\t", header=None).to_numpy(dtype=float)
    expected = confounds.to_numpy(dtype=float)
    if actual.shape != expected.shape or not np.isfinite(actual).all() or not np.allclose(
        actual, expected, rtol=1e-10, atol=1e-12
    ):
        raise ValueError("Existing confounds do not match current inputs; preserved unchanged for review")


def subject_filter_from_sublist(sublist: Path | None) -> set[str] | None:
    if sublist is None:
        return None
    return {f"sub-{sub}" for sub in read_subject_list(sublist)}


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fmriprep-dir", type=Path, default=repo_root / "derivatives" / "fmriprep")
    parser.add_argument("--tedana-dir", type=Path, default=repo_root / "derivatives" / "tedana")
    parser.add_argument("--output-dir", type=Path, default=repo_root / "derivatives" / "fsl" / "confounds_tedana")
    parser.add_argument("--sublist", type=Path, help="Optional subject list limiting which TEDANA outputs are processed.")
    parser.add_argument("--session", choices=("01", "02"))
    parser.add_argument("--expected-runs", type=int, help="Fail unless exactly this many metric files are selected.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--check", action="store_true", help="Verify alignment and existing matrices without writing.")
    parser.add_argument("--preserve-existing", action="store_true", help="Verify existing matrices; create missing ones only.")
    args = parser.parse_args()
    if args.expected_runs is not None and args.expected_runs < 1:
        parser.error("--expected-runs must be positive")

    metric_files = sorted(args.tedana_dir.rglob("*_desc-tedana_metrics.tsv"))
    allowed_subjects = subject_filter_from_sublist(args.sublist)
    failures = 0
    processed = 0
    for metric_file in metric_files:
        parsed = parse_metric_file(metric_file)
        sub = parsed["sub"]
        if allowed_subjects is not None and sub not in allowed_subjects:
            continue
        ses = parsed["ses"]
        if args.session is not None and ses != args.session:
            continue
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
            processed += 1
            failures += 1
            print(f"Missing confound input for {sub} ses-{ses} task-{task} run-{run}:")
            for path in missing:
                print(f"  {path}")
            continue

        processed += 1
        print(f"Making confounds: {sub} ses-{ses} task-{task} run-{run} -> {out_file}")
        if args.dry_run:
            continue
        try:
            confounds = build_confounds(fmriprep_file, mixing_file, metric_file)
            if args.check or args.preserve_existing:
                bold_file = fmriprep_file.with_name(
                    f"{sub}_ses-{ses}_task-{task}_run-{run}_echo-1_part-mag_desc-preproc_bold.nii.gz"
                )
                validate_alignment(confounds, bold_file)
                validate_alignment(confounds, base.with_name(f"{prefix}_desc-denoised_bold.nii.gz"))
            if args.check or (args.preserve_existing and out_file.exists()):
                verify_existing(confounds, out_file)
                print("VERIFIED existing confounds; unchanged")
            else:
                atomic_write_tsv(confounds, out_file, preserve_existing=args.preserve_existing)
        except Exception as exc:  # noqa: BLE001 - keep batch processing and report all failures.
            failures += 1
            print(f"Failed {sub} ses-{ses} task-{task} run-{run}: {exc}")

    print(f"Processed {processed} TEDANA metric file(s).")
    if (args.check or args.preserve_existing) and processed == 0:
        print("CHECK FAILED: no selected TEDANA metric files")
        failures += 1
    if args.expected_runs is not None and processed != args.expected_runs:
        print(f"CHECK FAILED: expected {args.expected_runs} runs, found {processed}")
        failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
