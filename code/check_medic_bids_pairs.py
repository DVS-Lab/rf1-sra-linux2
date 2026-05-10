#!/usr/bin/env python3
"""Check BIDS mag/phase multi-echo BOLD pairing for MEDIC/warpkit tests."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path


def _strip_nii_suffix(path: Path) -> str:
    name = path.name
    if name.endswith(".nii.gz"):
        return name[:-7]
    if name.endswith(".nii"):
        return name[:-4]
    return path.stem


def _parse_bids_name(path: Path):
    stem = _strip_nii_suffix(path)
    fields = stem.split("_")
    if not fields or fields[-1] != "bold":
        return None

    entities = []
    for field in fields[:-1]:
        if "-" not in field:
            continue
        key, value = field.split("-", 1)
        entities.append((key, value))

    ent = dict(entities)
    part = ent.get("part")
    echo = ent.get("echo")
    if part not in {"mag", "phase"} or echo is None:
        return None

    key = tuple((k, v) for k, v in entities if k not in {"part", "echo"})
    return key, part, echo


def _echo_sort_key(echo: str):
    try:
        return int(echo)
    except ValueError:
        return echo


def _shape(path: Path):
    import nibabel as nb

    return nb.load(path).shape


def _nvols(shape):
    return shape[3] if len(shape) > 3 else 1


def _label(group_key) -> str:
    return "_".join(f"{k}-{v}" for k, v in group_key)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether part-mag and part-phase multi-echo BOLD files have "
            "matching echo sets and matching NIfTI shapes/timepoint counts."
        )
    )
    parser.add_argument("bids_dir", type=Path, help="BIDS dataset root, e.g. ds006072")
    parser.add_argument(
        "--subject",
        help="Optional subject label, e.g. sub-P1R. If omitted, all subjects are scanned.",
    )
    parser.add_argument(
        "--only-problems",
        action="store_true",
        help="Only print groups with mismatches.",
    )
    args = parser.parse_args()

    try:
        import nibabel  # noqa: F401
    except ImportError:
        raise SystemExit(
            "This script needs nibabel. Install with `python -m pip install nibabel` "
            "or run it in an environment/container that already has nibabel."
        )

    search_root = args.bids_dir / args.subject if args.subject else args.bids_dir
    files = sorted(search_root.rglob("*_part-*_bold.nii*"))
    groups = defaultdict(lambda: {"mag": {}, "phase": {}})

    for path in files:
        parsed = _parse_bids_name(path)
        if parsed is None:
            continue
        group_key, part, echo = parsed
        groups[group_key][part][echo] = path

    if not groups:
        print(f"No part-mag/part-phase BOLD files found under {search_root}")
        return 1

    n_problem_groups = 0
    n_ok_groups = 0

    for group_key, parts in sorted(groups.items(), key=lambda item: _label(item[0])):
        mag = parts["mag"]
        phase = parts["phase"]
        mag_echoes = set(mag)
        phase_echoes = set(phase)
        shared_echoes = sorted(mag_echoes & phase_echoes, key=_echo_sort_key)
        problems = []

        if mag_echoes != phase_echoes:
            problems.append(
                "echo mismatch: "
                f"mag={sorted(mag_echoes, key=_echo_sort_key)}, "
                f"phase={sorted(phase_echoes, key=_echo_sort_key)}"
            )

        rows = []
        reference_shape = None
        for echo in shared_echoes:
            mag_shape = _shape(mag[echo])
            phase_shape = _shape(phase[echo])
            rows.append((echo, mag_shape, phase_shape, mag[echo], phase[echo]))

            if mag_shape != phase_shape:
                problems.append(
                    f"echo-{echo} shape mismatch: mag={mag_shape}, phase={phase_shape}"
                )
            elif _nvols(mag_shape) != _nvols(phase_shape):
                problems.append(
                    f"echo-{echo} timepoint mismatch: "
                    f"mag={_nvols(mag_shape)}, phase={_nvols(phase_shape)}"
                )

            if reference_shape is None:
                reference_shape = mag_shape
            if mag_shape != reference_shape:
                problems.append(
                    f"echo-{echo} mag shape differs from echo-"
                    f"{shared_echoes[0]}: {mag_shape} vs {reference_shape}"
                )
            if phase_shape != reference_shape:
                problems.append(
                    f"echo-{echo} phase shape differs from echo-"
                    f"{shared_echoes[0]}: {phase_shape} vs {reference_shape}"
                )

        if problems:
            n_problem_groups += 1
        else:
            n_ok_groups += 1

        if args.only_problems and not problems:
            continue

        status = "PROBLEM" if problems else "OK"
        print(f"\n[{status}] {_label(group_key)}")
        print(
            "  echoes: "
            f"mag={sorted(mag_echoes, key=_echo_sort_key)} "
            f"phase={sorted(phase_echoes, key=_echo_sort_key)}"
        )
        for echo, mag_shape, phase_shape, _mag_path, _phase_path in rows:
            print(f"  echo-{echo}: mag_shape={mag_shape} phase_shape={phase_shape}")
        for problem in problems:
            print(f"  - {problem}")

    print(
        f"\nSummary: {n_ok_groups} matched run group(s), "
        f"{n_problem_groups} problem run group(s)."
    )
    return 1 if n_problem_groups else 0


if __name__ == "__main__":
    raise SystemExit(main())
