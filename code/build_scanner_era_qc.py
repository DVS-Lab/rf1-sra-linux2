#!/usr/bin/env python3
"""Stratify canonical RF1-SRA run QC metrics by scanner software era."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from pipeline_utils import apply_umask_mode, ensure_safe_child_path


ERAS = ("E11", "XA30", "XA60")
METRICS = {
    "tsnr": ("tSNR", "tsnr_outlier"),
    "fd_mean": ("Mean framewise displacement", "fd_mean_outlier"),
    "tedana_rejected_components": (
        "TEDANA rejected components",
        "tedana_outlier",
    ),
    "brain_coverage_pct": ("Brain coverage (%)", "brain_coverage_outlier"),
}
SMOOTHNESS = {
    "fwhm_avg_mm": ("MRIQC smoothness: mean FWHM (mm)", None),
    "fwhm_avg": ("MRIQC mean FWHM (voxels)", None),
    **{f"fwhm_{axis}_mm": (f"MRIQC FWHM {axis} (mm)", None) for axis in "xyz"},
}
SUMMARY_METRICS = {**METRICS, **SMOOTHNESS}
PLOT_METRICS = {key: value for key, value in METRICS.items() if key != "brain_coverage_pct"}
PLOT_METRICS["fwhm_avg_mm"] = SMOOTHNESS["fwhm_avg_mm"]
RUN_COLUMNS = (
    "subject",
    "session",
    "paradigm",
    "task",
    "run",
    "software_era",
    *METRICS,
    *(flag for _label, flag in METRICS.values()),
    "imaging_qc_outlier",
    "qc_status",
    "bids_sidecar",
    *SMOOTHNESS,
    *(f"fwhm_{axis}" for axis in "xyz"),
    *(f"spacing_{axis}" for axis in "xyz"),
    "smoothness_status", "mriqc_json", "mriqc_version",
)
SUMMARY_COLUMNS = (
    "paradigm",
    "task",
    "session",
    "metric",
    "software_era",
    "n",
    "n_subjects", "n_total_runs", "n_missing",
    "mean",
    "std",
    "q1",
    "median",
    "q3",
    "minimum",
    "maximum",
    "cohort_fence",
    "outlier_direction",
    "cohort_outlier_n",
    "cohort_outlier_pct",
    "median_delta_from_e11",
    "median_pct_delta_from_e11",
    "median_delta_from_xa30", "median_pct_delta_from_xa30",
)
PARADIGMS = ("sharedreward", "trust", "ugr", "socialdoors")
OUTPUTS = (
    Path("run_metrics.tsv"),
    Path("summary.tsv"),
    Path("report.md"),
    Path("provenance.json"),
)


def figure_outputs(rows):
    return [Path("figures") / f"task-{task}_ses-{session}_by_scanner_era.png"
            for task, session in sorted({(r["task"], r["session"]) for r in rows})]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def output_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return f"{value:.17g}"
    return value


def write_tsv(path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({column: output_value(row.get(column)) for column in columns})
    apply_umask_mode(path)


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def parse_bool(value: Any) -> bool | None:
    normalized = str(value or "").strip().upper()
    if normalized == "TRUE":
        return True
    if normalized == "FALSE":
        return False
    if not normalized:
        return None
    raise ValueError(f"invalid canonical boolean: {value}")


def software_era(value: Any) -> str:
    normalized = str(value or "").upper().replace("SYNGO MR", "").strip()
    for era in ERAS:
        if era in normalized:
            return era
    return "unknown"


def linear_quantile(values: Iterable[float], q: float) -> float:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        raise ValueError("cannot calculate a quantile from no finite values")
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def sidecar_for_bold(project: Path, bold_value: str) -> Path:
    paths = [item for item in bold_value.split(";") if item]
    if len(paths) != 1:
        raise ValueError("canonical run has missing or ambiguous BIDS BOLD path")
    relative = Path(paths[0])
    if relative.is_absolute() or not relative.as_posix().endswith(".nii.gz"):
        raise ValueError(f"unsafe or invalid canonical BIDS BOLD path: {paths[0]}")
    bold = (project / relative).resolve()
    try:
        bold.relative_to(project)
    except ValueError as exc:
        raise ValueError(f"BIDS BOLD path escapes project root: {paths[0]}") from exc
    return Path(str(bold)[: -len(".nii.gz")] + ".json")


def load_run_metrics(
    project: Path, run_qc_path: Path
) -> tuple[list[dict[str, Any]], list[Path]]:
    records = read_tsv(run_qc_path)
    if not records:
        raise ValueError("canonical run_qc.tsv is empty")
    required = {
        "subject",
        "session",
        "paradigm",
        "task",
        "run",
        "bids_bold",
        "imaging_qc_outlier",
        "qc_status",
        "mriqc_json",
        *METRICS,
        *(flag for _label, flag in METRICS.values()),
    }
    missing_columns = sorted(required - set(records[0]))
    if missing_columns:
        raise ValueError(
            "canonical run_qc.tsv lacks required columns: " + ", ".join(missing_columns)
        )
    rows: list[dict[str, Any]] = []
    sidecars: list[Path] = []
    failures: list[str] = []
    for record in records:
        key = (
            f"sub-{record['subject']}_ses-{record['session']}_"
            f"task-{record['task']}_run-{record['run']}"
        )
        try:
            sidecar = sidecar_for_bold(project, record["bids_bold"])
            if not sidecar.is_file():
                raise ValueError(f"BIDS sidecar not found: {sidecar.relative_to(project)}")
            metadata = json.loads(sidecar.read_text())
            era = software_era(metadata.get("SoftwareVersions"))
            if era == "unknown":
                raise ValueError(
                    "unrecognized SoftwareVersions: "
                    + repr(metadata.get("SoftwareVersions", ""))
                )
            row: dict[str, Any] = {
                "subject": record["subject"],
                "session": record["session"],
                "paradigm": record["paradigm"],
                "task": record["task"],
                "run": record["run"],
                "software_era": era,
                "imaging_qc_outlier": parse_bool(record["imaging_qc_outlier"]),
                "qc_status": record["qc_status"],
                "bids_sidecar": sidecar.relative_to(project).as_posix(),
            }
            for metric, (_label, flag) in METRICS.items():
                row[metric] = finite(record[metric])
                row[flag] = parse_bool(record[flag])
            smoothness, sources = load_smoothness(project, record)
            row.update(smoothness)
            sidecars.extend(sources)
            rows.append(row)
            sidecars.append(sidecar)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            failures.append(f"{key}: {exc}")
    if failures:
        preview = "\n  ".join(failures[:25])
        suffix = "" if len(failures) <= 25 else f"\n  ... {len(failures) - 25} more"
        raise ValueError(f"scanner era could not be resolved for {len(failures)} run(s):\n  {preview}{suffix}")
    return rows, sidecars


def load_smoothness(project: Path, record: dict[str, str]) -> tuple[dict, list[Path]]:
    """MRIQC 24 functional IQMs store FWHM in voxels, spacing in mm."""
    row = {key: None for key in (*SMOOTHNESS, *(f"fwhm_{a}" for a in "xyz"),
                                *(f"spacing_{a}" for a in "xyz"))}
    row.update(mriqc_json=record["mriqc_json"], mriqc_version="",
               smoothness_status="missing_mriqc_json")
    names = [name for name in record["mriqc_json"].split(";") if name]
    if len(names) != 1:
        if names:
            row["smoothness_status"] = "ambiguous_mriqc_json"
        return row, []
    path = (project / names[0]).resolve()
    if Path(names[0]).is_absolute() or not path.is_relative_to(project / "derivatives/mriqc"):
        raise ValueError("MRIQC JSON path escapes canonical derivative root")
    prefix = f"sub-{record['subject']}_ses-{record['session']}_task-{record['task']}_run-{record['run']}_"
    if not path.name.startswith(prefix) or not path.name.endswith("bold.json"):
        raise ValueError("MRIQC JSON does not match canonical run identity")
    if not path.is_file():
        return row, []
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("expected JSON object")
    except (ValueError, OSError):
        row["smoothness_status"] = "invalid_mriqc_json"
        return row, [path]
    provenance = data.get("provenance", {})
    row["mriqc_version"] = str(provenance.get("version", "")) if isinstance(provenance, dict) else ""
    for key in ("fwhm_avg", *(f"fwhm_{a}" for a in "xyz"), *(f"spacing_{a}" for a in "xyz")):
        value = finite(data.get(key))
        row[key] = value if value is not None and value > 0 else None
    for axis in "xyz":
        width, spacing = row[f"fwhm_{axis}"], row[f"spacing_{axis}"]
        if width is not None and spacing is not None:
            row[f"fwhm_{axis}_mm"] = width * spacing
    widths = [row[f"fwhm_{axis}_mm"] for axis in "xyz"]
    if all(value is not None for value in widths):
        row["fwhm_avg_mm"] = sum(widths) / 3
    row["smoothness_status"] = "available" if all(row[k] is not None for k in SMOOTHNESS) else "missing_or_invalid_fwhm_or_spacing"
    return row, [path]


def load_thresholds(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    records = read_tsv(path)
    lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        if not record.get("task") or not record.get("session"):
            raise ValueError("legacy pooled thresholds: regenerate exact task/session QC first")
        direction = record.get("outlier_direction", "")
        if direction not in {"lower", "upper"}:
            raise ValueError("invalid threshold direction")
        fence_column = "lower_fence" if direction == "lower" else "upper_fence"
        key = (record["task"], record["session"], record.get("metric", ""))
        if key in lookup:
            raise ValueError("duplicate threshold key")
        lookup[key] = {
            "direction": direction,
            "fence": finite(record.get(fence_column)),
        }
    expected = {(task, session, metric) for task, session, _ in lookup for metric in METRICS}
    if not lookup or set(lookup) != expected:
        raise ValueError("thresholds.tsv lacks the complete task/session metric grid")
    return lookup


def summarize(
    rows: Sequence[dict[str, Any]],
    thresholds: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped = defaultdict(list)
    for row in rows:
        for metric in SUMMARY_METRICS:
            if row.get(metric) is not None:
                grouped[(row["task"], row["session"], metric, row["software_era"])].append(row)
    output: list[dict[str, Any]] = []
    for task, session in sorted({(r["task"], r["session"]) for r in rows}):
        for metric, (_label, flag) in SUMMARY_METRICS.items():
            for era in ERAS:
                group = grouped.get((task, session, metric, era), [])
                values = [float(row[metric]) for row in group]
                all_rows = [r for r in rows if (r["task"], r["session"], r["software_era"]) == (task, session, era)]
                if not all_rows:
                    continue
                mean = sum(values) / len(values) if values else None
                std = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values)) if values else None
                threshold = thresholds.get((task, session, metric), {"fence": None, "direction": None})
                output.append(
                    {
                        "paradigm": all_rows[0]["paradigm"],
                        "task": task,
                        "session": session,
                        "metric": metric,
                        "software_era": era,
                        "n": len(values),
                        "n_subjects": len({r["subject"] for r in group}),
                        "n_total_runs": len(all_rows),
                        "n_missing": len(all_rows) - len(values),
                        "mean": mean,
                        "std": std,
                        "q1": linear_quantile(values, 0.25) if values else None,
                        "median": linear_quantile(values, 0.5) if values else None,
                        "q3": linear_quantile(values, 0.75) if values else None,
                        "minimum": min(values) if values else None,
                        "maximum": max(values) if values else None,
                        "cohort_fence": threshold["fence"],
                        "outlier_direction": threshold["direction"],
                        "cohort_outlier_n": sum(row.get(flag) is True for row in group) if flag and group else None,
                        "cohort_outlier_pct": 100.0
                        * sum(row.get(flag) is True for row in group)
                        / len(group) if flag and group else None,
                    }
                )
    baselines = {
        (row["task"], row["session"], row["metric"], row["software_era"]): row["median"]
        for row in output
    }
    for row in output:
        for era in ("E11", "XA30"):
            baseline = baselines.get((row["task"], row["session"], row["metric"], era))
            delta = row["median"] - baseline if baseline is not None and row["median"] is not None else None
            row[f"median_delta_from_{era.lower()}"] = delta
            row[f"median_pct_delta_from_{era.lower()}"] = 100 * delta / abs(baseline) if delta is not None and baseline else None
    return output


def plot_scanner_eras(
    rows: Sequence[dict[str, Any]],
    thresholds: dict[tuple[str, str, str], dict[str, Any]],
    directory: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    colors = {"E11": "#4C78A8", "XA30": "#E3A018", "XA60": "#2A9D6F"}
    directory.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(
        {
            "font.size": 9,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    ):
        for task, session in sorted({(r["task"], r["session"]) for r in rows}):
            group = [row for row in rows if (row["task"], row["session"]) == (task, session)]
            fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
            for axis, (metric, (label, _flag)) in zip(
                axes.flat, PLOT_METRICS.items(), strict=True
            ):
                era_values = {
                    era: sorted(
                        float(row[metric])
                        for row in group
                        if row["software_era"] == era and row.get(metric) is not None
                    )
                    for era in ERAS
                }
                present = [era for era in ERAS if era_values[era]]
                positions = [ERAS.index(era) + 1 for era in present]
                if present:
                    boxes = axis.boxplot(
                        [era_values[era] for era in present],
                        positions=positions,
                        widths=0.55,
                        patch_artist=True,
                        showfliers=False,
                        medianprops={"color": "#202124", "linewidth": 1.5},
                        whiskerprops={"color": "#555555"},
                        capprops={"color": "#555555"},
                    )
                    for box, era in zip(boxes["boxes"], present, strict=True):
                        box.set_facecolor(colors[era])
                        box.set_alpha(0.65)
                    for era, position in zip(present, positions, strict=True):
                        values = era_values[era]
                        if len(values) == 1:
                            offsets = [0.0]
                        else:
                            offsets = [
                                -0.2 + 0.4 * index / (len(values) - 1)
                                for index in range(len(values))
                            ]
                        axis.scatter(
                            [position + offset for offset in offsets],
                            values,
                            s=8,
                            alpha=0.22,
                            color=colors[era],
                            edgecolors="none",
                            rasterized=True,
                        )
                else:
                    axis.text(0.5, 0.5, "No available measurements", ha="center",
                              transform=axis.transAxes)
                threshold = thresholds.get((task, session, metric), {"fence": None})
                if threshold["fence"] is not None:
                    axis.axhline(
                        float(threshold["fence"]),
                        color="#C23B22",
                        linewidth=1.5,
                        linestyle="--",
                        label="Task/session fence",
                    )
                    axis.legend(loc="best", frameon=False, fontsize=8)
                axis.set_xticks(
                    range(1, len(ERAS) + 1),
                    [f"{era}\nn={len(era_values[era])}" for era in ERAS],
                )
                axis.set_xlim(0.5, len(ERAS) + 0.5)
                axis.set_title(label + ("\nDescriptive only; no exclusion threshold"
                                       if metric in SMOOTHNESS else ""))
                axis.set_ylabel(label)
                axis.grid(axis="y", color="#E5E7EB", linewidth=0.7)
            fig.suptitle(
                f"RF1-SRA task-{task} ses-{session} QC by scanner era", fontsize=14
            )
            path = directory / f"task-{task}_ses-{session}_by_scanner_era.png"
            fig.savefig(
                path,
                dpi=180,
                metadata={"Software": "rf1-sra-linux2 build_scanner_era_qc.py"},
            )
            plt.close(fig)
            apply_umask_mode(path)


def fmt(value: Any, digits: int = 3) -> str:
    parsed = finite(value)
    return "NA" if parsed is None else f"{parsed:.{digits}g}"


def make_report(
    rows: Sequence[dict[str, Any]], summary: Sequence[dict[str, Any]], path: Path
) -> None:
    era_counts = {
        era: [row for row in rows if row["software_era"] == era] for era in ERAS
    }
    lookup = {
        (row["task"], row["session"], row["metric"], row["software_era"]): row
        for row in summary
    }
    lines = [
        "# RF1-SRA Imaging QC By Scanner Era",
        "",
        "This report stratifies the canonical run-level QC metrics by the scanner",
        "software era recorded in each BIDS echo-2 magnitude sidecar. It does not",
        "recalculate thresholds within era and does not authorize exclusions.",
        "Scanner era is associated with acquisition date and cohort composition, so",
        "between-era differences are descriptive and should not be read as causal.",
        "Coverage remains in the underlying table and policy; only its plot panel is replaced.",
        "Smoothness is MRIQC's functional FWHM estimate, not the FEAT smoothing kernel",
        "or smoothness measured on the final fMRIPrep/L1 outputs. No smoothness exclusion is applied.",
        "MRIQC reports FWHM in voxels. Each axis is multiplied by its own MRIQC spacing",
        "in mm; the plotted value is the arithmetic mean of those three mm estimates.",
        "Source: https://github.com/nipreps/mriqc/blob/24.0.2/mriqc/interfaces/functional.py",
        "",
        "## Inventory",
        "",
        "| Era | Runs | Participants | Participant-sessions |",
        "| --- | ---: | ---: | ---: |",
    ]
    for era in ERAS:
        group = era_counts[era]
        lines.append(
            f"| {era} | {len(group)} | "
            f"{len({row['subject'] for row in group})} | "
            f"{len({(row['subject'], row['session']) for row in group})} |"
        )
    for task, session in sorted({(r["task"], r["session"]) for r in rows}):
        lines.extend(
            [
                "",
                f"## Task {task}, Session {session}",
                "",
                "Values are median [Q1, Q3].",
                "",
                "| Metric | E11 | XA30 | XA60 |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for metric, (label, _flag) in PLOT_METRICS.items():
            cells = []
            for era in ERAS:
                item = lookup.get((task, session, metric, era))
                cells.append(
                    "NA"
                    if item is None
                    else f"{fmt(item['median'])} [{fmt(item['q1'])}, {fmt(item['q3'])}]"
                )
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        smooth = lookup.get((task, session, "fwhm_avg_mm", "XA60"))
        if smooth:
            lines.extend(["", f"XA60 minus XA30 median FWHM: {fmt(smooth['median_delta_from_xa30'])} mm "
                          f"({fmt(smooth['median_pct_delta_from_xa30'])}%)."])
        lines.extend(["", "| Era | FWHM runs / total | Participants with FWHM | Missing FWHM |",
                      "| --- | ---: | ---: | ---: |"])
        for era in ERAS:
            item = lookup.get((task, session, "fwhm_avg_mm", era))
            if item:
                lines.append(f"| {era} | {item['n']} / {item['n_total_runs']} | {item['n_subjects']} | {item['n_missing']} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Use `summary.tsv` for exact sample sizes, distributions, task/session-fence",
            "flag rates, axis-specific FWHM, missingness, and median differences from E11 and XA30.",
            "All measurements are retained regardless of QC flags. Repeated runs are not",
            "independent participants; these are run-level descriptive comparisons, not significance tests.",
            "Inspect voxel spacing and MRIQC versions in run_metrics.tsv before interpreting differences.",
            "Large differences should be",
            "followed by task/session-stratified and, where possible, within-subject",
            "review before attributing them to scanner software or sequence changes.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")
    apply_umask_mode(path)


def input_inventory_digest(paths: Iterable[Path], project: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted({item.resolve() for item in paths}):
        digest.update(path.relative_to(project).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def install(stage: Path, output: Path) -> None:
    backup = output.with_name(f".{output.name}.backup")
    if backup.exists():
        shutil.rmtree(backup)
    if output.exists():
        output.rename(backup)
    try:
        stage.rename(output)
    except Exception:
        if backup.exists() and not output.exists():
            backup.rename(output)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def build(args: argparse.Namespace) -> int:
    project = args.project_root.expanduser().resolve()
    output = ensure_safe_child_path(project / "qc", args.output_dir)
    run_qc = args.run_qc.expanduser().resolve()
    thresholds_path = args.thresholds.expanduser().resolve()
    rows, sidecars = load_run_metrics(project, run_qc)
    thresholds = load_thresholds(thresholds_path)
    summary = summarize(rows, thresholds)
    era_counts = {era: sum(row["software_era"] == era for row in rows) for era in ERAS}
    print(f"Scanner-era QC runs: {len(rows)}")
    print("Era counts: " + ", ".join(f"{era}={era_counts[era]}" for era in ERAS))
    print(f"Smoothness available (mm): {sum(row['fwhm_avg_mm'] is not None for row in rows)}/{len(rows)}")
    print(f"Tracked output: {output}")
    if args.dry_run:
        print("DRY RUN: no scanner-era QC outputs were written.")
        return 0
    if output.exists() and not args.overwrite:
        raise ValueError(f"output exists; review it or use --overwrite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".scanner-era-qc-", dir=output.parent) as temp:
        stage = Path(temp) / "scanner_era"
        stage.mkdir()
        write_tsv(stage / "run_metrics.tsv", rows, RUN_COLUMNS)
        write_tsv(stage / "summary.tsv", summary, SUMMARY_COLUMNS)
        plot_scanner_eras(rows, thresholds, stage / "figures")
        make_report(rows, summary, stage / "report.md")
        provenance = {
            "schema_version": 2,
            "generated_at": utc_now(),
            "reporting_code_sha256": sha256(Path(__file__)),
            "run_qc": run_qc.relative_to(project).as_posix(),
            "run_qc_sha256": sha256(run_qc),
            "thresholds": thresholds_path.relative_to(project).as_posix(),
            "thresholds_sha256": sha256(thresholds_path),
            "software_era_source": "BIDS echo-2 part-mag SoftwareVersions",
            "allowed_software_eras": list(ERAS),
            "unknown_software_eras": 0,
            "source_json_count": len(set(sidecars)),
            "source_json_inventory_sha256": input_inventory_digest(sidecars, project),
            "smoothness_source": "canonical MRIQC JSON: axis FWHM voxels times axis spacing mm",
            "smoothness_exclusion_authorized": False,
            "plot_metrics": list(PLOT_METRICS),
            "causal_claim_authorized": False,
            "era_specific_thresholds_calculated": False,
            "threshold_grouping": ["task", "session"],
            "outputs": {},
        }
        for relative in (*OUTPUTS, *figure_outputs(rows)):
            if relative.name != "provenance.json":
                provenance["outputs"][relative.as_posix()] = sha256(stage / relative)
        provenance_path = stage / "provenance.json"
        provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        apply_umask_mode(provenance_path)
        install(stage, output)
    print(f"Scanner-era QC report: {output / 'report.md'}")
    return 0


def compare_rows(
    stored: Sequence[dict[str, str]],
    expected: Sequence[dict[str, Any]],
    columns: Sequence[str],
) -> bool:
    if len(stored) != len(expected):
        return False
    for actual, target in zip(stored, expected, strict=True):
        for column in columns:
            if actual.get(column, "") != str(output_value(target.get(column))):
                return False
    return True


def check(args: argparse.Namespace) -> int:
    project = args.project_root.expanduser().resolve()
    output = ensure_safe_child_path(project / "qc", args.output_dir)
    run_qc = args.run_qc.expanduser().resolve()
    thresholds_path = args.thresholds.expanduser().resolve()
    failures: list[str] = []
    try:
        rows, sidecars = load_run_metrics(project, run_qc)
        thresholds = load_thresholds(thresholds_path)
        summary = summarize(rows, thresholds)
    except (OSError, ValueError) as exc:
        print(f"CHECK FAILED: live input error: {exc}")
        return 1
    provenance_path = output / "provenance.json"
    try:
        provenance = json.loads(provenance_path.read_text())
    except (OSError, json.JSONDecodeError):
        provenance = {}
        failures.append("missing or invalid provenance.json")
    for relative in (*OUTPUTS, *figure_outputs(rows)):
        path = output / relative
        if not path.is_file():
            failures.append(f"missing output: {relative}")
        elif relative.name != "provenance.json" and provenance.get("outputs", {}).get(
            relative.as_posix()
        ) != sha256(path):
            failures.append(f"output checksum mismatch: {relative}")
    if provenance.get("schema_version") != 2:
        failures.append("unsupported provenance schema")
    if provenance.get("reporting_code_sha256") != sha256(Path(__file__)):
        failures.append("reporting code changed; rebuild scanner-era report")
    if provenance.get("smoothness_exclusion_authorized") is not False or provenance.get("plot_metrics") != list(PLOT_METRICS):
        failures.append("incorrect smoothness policy or plot metrics")
    if provenance.get("causal_claim_authorized") is not False:
        failures.append("provenance lacks noncausal interpretation guard")
    if provenance.get("era_specific_thresholds_calculated") is not False:
        failures.append("provenance indicates era-specific thresholds")
    if provenance.get("run_qc_sha256") != sha256(run_qc):
        failures.append("run_qc.tsv checksum mismatch")
    if provenance.get("thresholds_sha256") != sha256(thresholds_path):
        failures.append("thresholds.tsv checksum mismatch")
    if provenance.get("source_json_inventory_sha256") != input_inventory_digest(
        sidecars, project
    ):
        failures.append("BIDS/MRIQC JSON inventory checksum mismatch")
    run_path = output / "run_metrics.tsv"
    if run_path.is_file() and not compare_rows(read_tsv(run_path), rows, RUN_COLUMNS):
        failures.append("run_metrics.tsv disagrees with live canonical QC/BIDS inputs")
    summary_path = output / "summary.tsv"
    if summary_path.is_file() and not compare_rows(
        read_tsv(summary_path), summary, SUMMARY_COLUMNS
    ):
        failures.append("summary.tsv disagrees with recomputed scanner-era statistics")
    for failure in failures:
        print(f"CHECK FAILED: {failure}")
    if failures:
        return 1
    print(
        f"CHECK PASSED: scanner-era QC outputs match {len(rows)} canonical run(s) "
        "across E11, XA30, and XA60."
    )
    print(f"Smoothness available (mm): {sum(row['fwhm_avg_mm'] is not None for row in rows)}/{len(rows)}; no exclusions changed.")
    return 0


def parser() -> argparse.ArgumentParser:
    project = Path(__file__).resolve().parents[1]
    result = argparse.ArgumentParser(description=__doc__)
    children = result.add_subparsers(dest="command", required=True)
    for name in ("build", "check"):
        child = children.add_parser(name)
        child.add_argument("--project-root", type=Path, default=project)
        child.add_argument("--run-qc", type=Path, default=project / "qc" / "run_qc.tsv")
        child.add_argument(
            "--thresholds", type=Path, default=project / "qc" / "thresholds.tsv"
        )
        child.add_argument(
            "--output-dir", type=Path, default=project / "qc" / "scanner_era"
        )
    build_parser = children.choices["build"]
    build_parser.add_argument("--overwrite", action="store_true")
    build_parser.add_argument("--dry-run", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return build(args) if args.command == "build" else check(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
