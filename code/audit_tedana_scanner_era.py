#!/usr/bin/env python3
"""Forensically compare RF1 TEDANA inputs across E11, XA30, and XA60."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import nibabel as nib
import numpy as np
import pandas as pd

from audit_tedana_design import parse_mapca, software_era
from pipeline_utils import apply_umask_mode, ensure_safe_child_path


ERAS = ("E11", "XA30", "XA60")
PRIVATE_PATTERN = re.compile(
    r"patient|subject|institution|address|physician|operator|accession|birth|uid|serial|studyid|"
    r"acquisitiondate|acquisitiontime|contentdate|contenttime|seriesdate|seriestime|"
    r"studydate|studytime|instancedate|instancetime",
    re.I,
)
DICOM_SAFE_KEYWORDS = frozenset(
    {
        "AcquisitionContrast", "AcquisitionDuration", "AcquisitionMatrix", "AngioFlag",
        "BitsAllocated", "BitsStored", "BloodSignalNulling", "Columns",
        "ComplexImageComponent", "EchoNumbers", "EchoPlanarPulseSequence",
        "EchoPulseSequence", "EchoTime", "EchoTrainLength", "FlipAngle",
        "FlowCompensation", "FrameAcquisitionDuration", "FrameType",
        "GeometryOfKSpaceTraversal", "GradientEchoTrainLength", "HighBit", "ImageType",
        "ImagedNucleus", "ImagingFrequency", "InPlanePhaseEncodingDirection",
        "InversionRecovery", "KSpaceFiltering", "LossyImageCompression",
        "MRAcquisitionFrequencyEncodingSteps", "MRAcquisitionPhaseEncodingStepsInPlane",
        "MRAcquisitionType", "MagneticFieldStrength", "MagnetizationTransfer",
        "Manufacturer", "ManufacturerModelName", "Modality", "MultiPlanarExcitation",
        "NumberOfAverages", "NumberOfFrames", "NumberOfKSpaceTrajectories",
        "NumberOfPhaseEncodingSteps", "NumberOfTemporalPositions", "OperatingMode",
        "OperatingModeType", "OversamplingPhase", "ParallelAcquisition",
        "ParallelAcquisitionTechnique", "ParallelReductionFactorInPlane",
        "ParallelReductionFactorOutOfPlane", "PartialFourier", "PartialFourierDirection",
        "PercentPhaseFieldOfView", "PercentSampling", "PhaseContrast",
        "PhotometricInterpretation", "PixelBandwidth", "PixelRepresentation",
        "PixelSpacing", "PulseSequenceName", "RFEchoTrainLength",
        "RectilinearPhaseEncodeReordering", "RepetitionTime", "RescaleIntercept",
        "RescaleSlope", "RescaleType", "Rows", "SAR", "SamplesPerPixel",
        "SaturationRecovery", "ScanOptions", "ScanningSequence",
        "SegmentedKSpaceTraversal", "SequenceName", "SequenceVariant", "SliceThickness",
        "SoftwareVersions", "SpacingBetweenSlices", "SpatialPresaturation",
        "SpectrallySelectedExcitation", "SpectrallySelectedSuppression", "Spoiling",
        "SteadyStatePulseSequence", "T2Preparation", "Tagging", "TransmitterFrequency",
        "VariableFlipAngleFlag", "VolumeBasedCalculationTechnique",
        "VolumetricProperties",
    }
)
PROTOCOL_COLUMNS = (
    "task", "run", "echo", "parameter", "status", "eras_present",
    "e11_unique_values", "xa30_unique_values", "xa60_unique_values",
    "e11_n_values", "xa30_n_values", "xa60_n_values",
)
ECHO_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "software_versions", "software_era",
    "echo", "echo_time", "n_volumes", "brain_mask_voxels", "mean_signal",
    "median_temporal_standard_deviation", "median_tsnr", "median_standardized_dvars",
    "median_lag1_autocorrelation", "low_frequency_power_fraction",
    "high_frequency_power_fraction", "spectral_entropy", "echo_file",
)
RUN_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "software_versions", "software_era",
    "nss_count", "number_of_original_volumes", "brain_mask_voxels", "mean_fd",
    "pca_components", "aic_components", "kic_components", "mdl_components",
    "selected_fraction_possible", "selected_pca_variance", "pca_top10_variance",
    "pca_effective_rank", "echo_mean_signal_slope", "echo_tsnr_slope",
    "echo_standardized_dvars_slope", "audit_status", "audit_issues",
)
PAIR_METRICS = (
    "pca_components", "selected_fraction_possible", "selected_pca_variance",
    "brain_mask_voxels", "mean_fd", "echo_mean_signal_slope", "echo_tsnr_slope",
    "echo_standardized_dvars_slope",
)
PAIR_COLUMNS = (
    "subject", "task", "run", "first_session", "second_session", "first_era", "second_era",
    *(f"first_{metric}" for metric in PAIR_METRICS),
    *(f"second_{metric}" for metric in PAIR_METRICS),
    *(f"second_minus_first_{metric}" for metric in PAIR_METRICS),
)
DICOM_COLUMNS = (
    "task", "run", "software_era", "run_key", "series_number", "mapping_status",
)
OUTPUTS = (
    Path("protocol_parameters.tsv"), Path("echo_properties.tsv"), Path("run_properties.tsv"),
    Path("within_subject_pairs.tsv"), Path("dicom_representatives.tsv"),
    Path("dicom_parameters.tsv"), Path("report.md"), Path("provenance.json"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle: return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    apply_umask_mode(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def inventory_digest(paths: Sequence[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(item.resolve() for item in paths)):
        stat = path.stat(); digest.update(path.relative_to(root).as_posix().encode())
        digest.update(f"\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def normalized_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    output: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            if not PRIVATE_PATTERN.search(name): output.update(flatten_json(item, name))
    elif isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value): output[prefix] = value
        else:
            for index, item in enumerate(value): output.update(flatten_json(item, f"{prefix}[{index}]"))
    else: output[prefix] = value
    return output


def protocol_records(project: Path, rows: Sequence[dict[str, str]]) -> tuple[list[dict[str, Any]], list[Path]]:
    records = []; inputs = []
    for row in rows:
        if row.get("audit_status") != "complete": continue
        for echo, relative in enumerate(filter(None, row["echo_jsons"].split(";")), start=1):
            path = project / relative; payload = json.loads(path.read_text()); inputs.append(path)
            for parameter, value in flatten_json(payload).items():
                records.append(
                    {
                        "task": row["task"], "run": row["run"], "echo": str(echo),
                        "parameter": parameter, "software_era": software_era(row["software_versions"]),
                        "value": normalized_value(value),
                    }
                )
    return records, inputs


def summarize_protocol(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in records: groups[(row["task"], row["run"], row["echo"], row["parameter"])][row["software_era"]].add(row["value"])
    output = []
    for (task, run, echo, parameter), values in sorted(groups.items()):
        present = [era for era in ERAS if era in values]
        within = any(len(values[era]) > 1 for era in present)
        sets = [values[era] for era in present]
        if within: status = "varies_within_era"
        elif len(present) < 2: status = "insufficient_cross_era_coverage"
        elif all(item == sets[0] for item in sets[1:]): status = "identical_across_eras"
        else: status = "differs_systematically_by_era"
        row = {"task": task, "run": run, "echo": echo, "parameter": parameter, "status": status, "eras_present": ";".join(present)}
        for era in ERAS:
            key = era.lower(); unique = sorted(values.get(era, set()))
            row[f"{key}_unique_values"] = ";".join(unique); row[f"{key}_n_values"] = len(unique)
        output.append(row)
    return output


def correlation(first: np.ndarray, second: np.ndarray) -> float:
    x = first - np.mean(first); y = second - np.mean(second)
    denominator = float(np.linalg.norm(x) * np.linalg.norm(y))
    return float(np.dot(x, y) / denominator) if denominator else math.nan


def lag1(data: np.ndarray) -> np.ndarray:
    first = data[:-1] - np.mean(data[:-1], axis=0); second = data[1:] - np.mean(data[1:], axis=0)
    denominator = np.linalg.norm(first, axis=0) * np.linalg.norm(second, axis=0)
    return np.divide(np.sum(first * second, axis=0), denominator, out=np.full(data.shape[1], np.nan), where=denominator > 0)


def spectral_metrics(data: np.ndarray, tr: float, cap: int = 2048) -> tuple[float, float, float]:
    indices = np.linspace(0, data.shape[1] - 1, min(cap, data.shape[1]), dtype=int)
    current = data[:, indices] - np.mean(data[:, indices], axis=0)
    power = np.abs(np.fft.rfft(current, axis=0)) ** 2; frequencies = np.fft.rfftfreq(len(current), tr)
    power = power[1:]; frequencies = frequencies[1:]
    total = np.sum(power, axis=0); valid = total > 0
    if not np.any(valid): return math.nan, math.nan, math.nan
    normalized = power[:, valid] / total[valid]
    low = np.sum(normalized[(frequencies > 0) & (frequencies < 0.10)], axis=0)
    high = np.sum(normalized[frequencies >= 0.20], axis=0)
    entropy = -np.sum(normalized * np.log(normalized + np.finfo(float).eps), axis=0) / math.log(len(frequencies))
    return float(np.median(low)), float(np.median(high)), float(np.median(entropy))


def echo_metrics(path: Path, mask: np.ndarray, tr: float) -> dict[str, float | int]:
    image = nib.load(str(path))
    if len(image.shape) != 4 or image.shape[:3] != mask.shape: raise ValueError(f"echo/mask shape mismatch: {path}")
    values = np.asarray(image.dataobj, dtype=np.float32)[mask].T.astype(np.float64)
    valid = np.all(np.isfinite(values), axis=0) & (np.std(values, axis=0) > 0); values = values[:, valid]
    if not values.shape[1]: raise ValueError(f"no valid echo voxels: {path}")
    sd = np.std(values, axis=0, ddof=1); tsnr = np.mean(values, axis=0) / sd
    dv = np.sqrt(np.mean(np.diff(values, axis=0) ** 2, axis=1)); standardized = dv / np.median(sd)
    low, high, entropy = spectral_metrics(values, tr)
    return {
        "n_volumes": len(values), "mean_signal": float(np.mean(values)),
        "median_temporal_standard_deviation": float(np.median(sd)), "median_tsnr": float(np.median(tsnr)),
        "median_standardized_dvars": float(np.median(standardized)),
        "median_lag1_autocorrelation": float(np.nanmedian(lag1(values))),
        "low_frequency_power_fraction": low, "high_frequency_power_fraction": high, "spectral_entropy": entropy,
    }


def pca_spectrum(path: Path) -> tuple[int, float, float, float]:
    frame = pd.read_csv(path, sep="\t")
    normalized = {str(column).strip().lower(): column for column in frame}
    column = normalized.get("normalized variance explained") or normalized.get("variance explained")
    if column is None: raise ValueError(f"PCA variance column missing: {path}")
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    values = values[np.isfinite(values) & (values >= 0)]
    if not len(values):
        raise ValueError(f"PCA variance values missing: {path}")
    # TEDANA versions have emitted this field as either fractions or percentages.
    # Preserve the selected variance total instead of normalizing it away.
    if float(np.sum(values)) > 1.5:
        values = values / 100.0
    total = float(np.sum(values))
    probabilities = values / total if total else np.zeros_like(values)
    entropy = -float(
        np.sum(probabilities * np.log(probabilities + np.finfo(float).eps))
    )
    return len(frame), total, float(np.sum(values[:10])), float(np.exp(entropy))


def slope(x: Sequence[float], y: Sequence[float]) -> float:
    return float(np.polyfit(np.asarray(x, dtype=float), np.asarray(y, dtype=float), 1)[0]) if len(x) > 1 else math.nan


def audit_run(project: Path, row: dict[str, str], skip_images: bool) -> tuple[dict[str, Any], list[dict[str, Any]], list[Path]]:
    common = {name: row[name] for name in ("subject", "session", "task", "run", "run_key", "software_versions")}
    common["software_era"] = software_era(row["software_versions"]); inputs = []
    try:
        pca_path = project / row["tedana_pca_metrics"]; cross = pca_path.with_name(f"{row['run_key']}_desc-PCACrossComponent_metrics.json")
        pca_count, selected_variance, top10, effective = pca_spectrum(pca_path); mapca = parse_mapca(cross); inputs.extend((pca_path, cross))
        echo_rows = []
        if skip_images:
            brain_voxels = ""
        else:
            mask_path = project / row["fmriprep_mask"]; mask = np.asarray(nib.load(str(mask_path)).dataobj) > 0; brain_voxels = int(np.sum(mask)); inputs.append(mask_path)
            echo_times = [float(value) for value in row["echo_times"].split(";")]
            echo_paths = [project / value for value in row["echo_files"].split(";")]
            for echo, (echo_time, echo_path) in enumerate(zip(echo_times, echo_paths), start=1):
                result = echo_metrics(echo_path, mask, float(row["repetition_time"])); inputs.append(echo_path)
                echo_rows.append({**common, "echo": echo, "echo_time": echo_time, "brain_mask_voxels": brain_voxels, "echo_file": echo_path.relative_to(project).as_posix(), **result})
        run_output = {
            **common, "nss_count": row["nss_count"], "number_of_original_volumes": row["number_of_original_volumes"],
            "brain_mask_voxels": brain_voxels, "mean_fd": row["mean_fd"], "pca_components": pca_count,
            "aic_components": mapca["aic_components"], "kic_components": mapca["kic_components"], "mdl_components": mapca["mdl_components"],
            "selected_fraction_possible": pca_count / int(row["number_of_steady_state_volumes"]),
            "selected_pca_variance": selected_variance, "pca_top10_variance": top10, "pca_effective_rank": effective,
            "echo_mean_signal_slope": slope([item["echo_time"] for item in echo_rows], [item["mean_signal"] for item in echo_rows]) if echo_rows else "",
            "echo_tsnr_slope": slope([item["echo_time"] for item in echo_rows], [item["median_tsnr"] for item in echo_rows]) if echo_rows else "",
            "echo_standardized_dvars_slope": slope([item["echo_time"] for item in echo_rows], [item["median_standardized_dvars"] for item in echo_rows]) if echo_rows else "",
            "audit_status": "complete", "audit_issues": "",
        }
        return run_output, echo_rows, inputs
    except Exception as exc:
        return {**common, "audit_status": "incomplete", "audit_issues": f"{type(exc).__name__}:{exc}"}, [], inputs


def within_subject_pairs(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["audit_status"] == "complete": groups[(row["subject"], row["task"], row["run"])].append(row)
    output = []
    for (subject, task, run), members in groups.items():
        for first_index, first in enumerate(sorted(members, key=lambda item: (item["session"], item["software_era"]))):
            for second in sorted(members, key=lambda item: (item["session"], item["software_era"]))[first_index + 1:]:
                if first["software_era"] == second["software_era"]: continue
                row = {"subject": subject, "task": task, "run": run, "first_session": first["session"], "second_session": second["session"], "first_era": first["software_era"], "second_era": second["software_era"]}
                for metric in PAIR_METRICS:
                    first_value, second_value = first.get(metric, ""), second.get(metric, "")
                    row[f"first_{metric}"] = first_value; row[f"second_{metric}"] = second_value
                    try:
                        difference = float(second_value) - float(first_value)
                    except (TypeError, ValueError):
                        difference = ""
                    row[f"second_minus_first_{metric}"] = difference
                output.append(row)
    return output


def source_scan(project: Path, source_root: Path, row: dict[str, str]) -> dict[str, Any]:
    json_path = project / row["echo_jsons"].split(";")[0]; payload = json.loads(json_path.read_text())
    series = payload.get("SeriesNumber", ""); description = payload.get("SeriesDescription", "")
    candidates = [source_root / f"Smith-SRA-{row['subject']}"]
    if row["session"] != "01": candidates.insert(0, source_root / f"Smith-SRA-{row['subject']}-{int(row['session'])}")
    scans = []
    for root in candidates:
        if root.is_dir(): scans.extend(root.rglob(f"scans/{series}-*"))
    scans = sorted(set(path for path in scans if path.is_dir()))
    dicoms = []
    for scan in scans: dicoms.extend(scan.rglob("*.dcm"))
    status = "mapped" if len(scans) == 1 and dicoms else "ambiguous" if len(scans) > 1 else "not_found"
    return {
        "task": row["task"], "run": row["run"], "software_era": software_era(row["software_versions"]), "run_key": row["run_key"],
        "series_number": series, "series_description": description,
        "source_scan_directory": str(scans[0]) if len(scans) == 1 else ";".join(map(str, scans)),
        "representative_dicom": str(sorted(dicoms)[0]) if len(scans) == 1 and dicoms else "", "mapping_status": status,
    }


def representative_rows(rows: Sequence[dict[str, str]], source_root: Path, project: Path) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("audit_status") == "complete": groups[(row["task"], row["run"], software_era(row["software_versions"]))].append(row)
    output = []
    for group in groups.values():
        ordered = sorted(group, key=lambda row: row["run_key"]); output.append(source_scan(project, source_root, ordered[len(ordered) // 2]))
    return sorted(output, key=lambda row: (row["task"], row["run"], row["software_era"]))


def dicom_parameters(
    representatives: Sequence[dict[str, Any]], skip_headers: bool = False
) -> list[dict[str, Any]]:
    mapped = [row for row in representatives if Path(row["representative_dicom"]).is_file()]
    if skip_headers or not mapped:
        return []
    try:
        import pydicom
    except ImportError as exc:
        raise RuntimeError(
            "pydicom is required for mapped raw-header comparisons; install it in "
            "the audit environment or explicitly use --skip-dicom-headers"
        ) from exc
    records = []
    for row in mapped:
        path = Path(row["representative_dicom"])
        if not path.is_file(): continue
        dataset = pydicom.dcmread(path, stop_before_pixels=True, force=True)
        for element in dataset.iterall():
            name = element.keyword or str(element.tag)
            if (
                name not in DICOM_SAFE_KEYWORDS
                or element.VR in {"DA", "DT", "PN", "SQ", "TM", "UI"}
                or element.tag.group == 0x0010
                or bool(getattr(element.tag, "is_private", False))
                or PRIVATE_PATTERN.search(name)
            ):
                continue
            value = normalized_value(str(element.value))
            records.append(
                {
                    "task": row["task"], "run": row["run"], "echo": "dicom",
                    "software_era": row["software_era"], "parameter": name,
                    "value": value,
                }
            )
    return records


def make_report(protocol: Sequence[dict[str, Any]], runs: Sequence[dict[str, Any]], pairs: Sequence[dict[str, Any]], dicoms: Sequence[dict[str, Any]], path: Path) -> None:
    counts = defaultdict(int)
    for row in protocol: counts[row["status"]] += 1
    complete = sum(row["audit_status"] == "complete" for row in runs)
    lines = [
        "# TEDANA Scanner-Era Forensic Audit", "",
        "This audit separates nominal acquisition metadata from reconstructed-image properties. Cross-era results are observational and do not establish that scanner software caused a difference.", "",
        "## Coverage", "", f"- Run properties complete: {complete}/{len(runs)}", f"- Within-subject cross-era pairs: {len(pairs)}",
        f"- Representative DICOM mappings: {sum(row['mapping_status'] == 'mapped' for row in dicoms)}/{len(dicoms)}", "",
        "## Sidecar Parameters", "", *(f"- {key}: {value}" for key, value in sorted(counts.items())), "",
        "## Interpretation Gate", "",
        "A parameter absent from BIDS is not assumed invariant. Review `dicom_representatives.tsv` before interpreting raw-header results. If nominal sequence fields remain matched while XA60 differs in temporal, spectral, echo-wise, or PCA-spectrum properties, describe this as an association with reconstructed-data/noise properties rather than a proven causal XA60 effect.",
    ]
    path.write_text("\n".join(lines) + "\n"); apply_umask_mode(path)


def build(args: argparse.Namespace) -> int:
    project = args.project_root.resolve(); output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    rows = read_tsv(args.current_runs); complete = [row for row in rows if row.get("audit_status") == "complete"]
    if args.dry_run:
        print(f"Would compare scanner-era metadata for {len(complete)} complete run(s).")
        print("Image properties: " + ("skipped" if args.skip_images else f"enabled with {args.jobs} worker(s)")); print(f"Tracked output: {output}"); return 0
    if output.exists() and not args.overwrite: raise ValueError(f"output exists; review it or use --overwrite: {output}")
    records, inputs = protocol_records(project, complete); protocol = summarize_protocol(records)
    run_rows = []; echo_rows = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(audit_run, project, row, args.skip_images): row for row in complete}
        for index, future in enumerate(as_completed(futures), start=1):
            run_row, echoes, paths = future.result(); run_rows.append(run_row); echo_rows.extend(echoes); inputs.extend(paths)
            if index % 25 == 0 or index == len(futures): print(f"Audited {index}/{len(futures)} scanner-era run(s).", flush=True)
    run_rows.sort(key=lambda row: row["run_key"]); echo_rows.sort(key=lambda row: (row["run_key"], row["echo"]))
    pairs = within_subject_pairs(run_rows); representatives = representative_rows(complete, args.source_root, project)
    dicom_rows = dicom_parameters(representatives, args.skip_dicom_headers)
    dicom_summary = summarize_protocol(dicom_rows) if dicom_rows else []
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tedana-scanner-era-", dir=output.parent) as temp:
        stage = Path(temp)
        write_tsv(stage / "protocol_parameters.tsv", protocol, PROTOCOL_COLUMNS); write_tsv(stage / "echo_properties.tsv", echo_rows, ECHO_COLUMNS)
        write_tsv(stage / "run_properties.tsv", run_rows, RUN_COLUMNS); write_tsv(stage / "within_subject_pairs.tsv", pairs, PAIR_COLUMNS)
        write_tsv(stage / "dicom_representatives.tsv", representatives, DICOM_COLUMNS); write_tsv(stage / "dicom_parameters.tsv", dicom_summary, PROTOCOL_COLUMNS)
        make_report(protocol, run_rows, pairs, representatives, stage / "report.md")
        provenance = {
            "schema_version": 1, "generated_at": utc_now(), "current_runs_sha256": sha256(args.current_runs),
            "runs": len(complete), "skip_images": args.skip_images, "jobs": args.jobs,
            "skip_dicom_headers": args.skip_dicom_headers,
            "input_inventory_digest_path_size_mtime": inventory_digest([args.current_runs.resolve(), *inputs], project),
            "identifiers_and_dates_excluded_from_metadata_tables": True,
            "dicom_scientific_keyword_allowlist_enforced": True,
            "dicom_representative_paths_redacted": True,
            "causal_claim_authorized": False,
            "outputs": {},
        }
        for item in OUTPUTS:
            if item.name != "provenance.json": provenance["outputs"][item.as_posix()] = sha256(stage / item)
        (stage / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n"); apply_umask_mode(stage / "provenance.json")
        backup = output.with_name(f".{output.name}.backup")
        if backup.exists(): shutil.rmtree(backup)
        if output.exists(): output.rename(backup)
        stage.rename(output)
        if backup.exists(): shutil.rmtree(backup)
    print(f"Scanner-era runs audited: {len(run_rows)}"); print(f"Tracked report: {output / 'report.md'}"); return 0


def check(args: argparse.Namespace) -> int:
    project = args.project_root.resolve(); output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    provenance_path = output / "provenance.json"; provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}; failures = []
    if not provenance: failures.append("missing_provenance")
    for item in OUTPUTS:
        path = output / item
        if not path.is_file(): failures.append(f"missing:{path}")
        elif item.name != "provenance.json" and provenance.get("outputs", {}).get(item.as_posix()) != sha256(path): failures.append(f"checksum:{path}")
    if provenance.get("current_runs_sha256") != sha256(args.current_runs): failures.append("current_runs_checksum")
    for failure in failures: print(f"FAILED {failure}")
    if failures: print(f"CHECK FAILED: {len(failures)} scanner-era issue(s)."); return 1
    print(f"CHECK PASSED: TEDANA scanner-era audit validated for {provenance['runs']} run(s)."); return 0


def parser() -> argparse.ArgumentParser:
    project = Path(__file__).resolve().parents[1]; result = argparse.ArgumentParser(description=__doc__); children = result.add_subparsers(dest="command", required=True)
    for name in ("build", "check"):
        child = children.add_parser(name); child.add_argument("--project-root", type=Path, default=project)
        child.add_argument("--current-runs", type=Path, default=project / "qc" / "tedana_audit" / "current_runs.tsv")
        child.add_argument("--output-dir", type=Path, default=project / "qc" / "tedana_audit" / "scanner_era")
        child.add_argument("--source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra"))
    build_parser = children.choices["build"]; build_parser.add_argument("--jobs", type=int, default=4); build_parser.add_argument("--skip-images", action="store_true")
    build_parser.add_argument("--skip-dicom-headers", action="store_true")
    build_parser.add_argument("--overwrite", action="store_true"); build_parser.add_argument("--dry-run", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if getattr(args, "jobs", 1) < 1: raise ValueError("--jobs must be positive")
        return build(args) if args.command == "build" else check(args)
    except Exception as exc: print(f"ERROR: {exc}"); return 1


if __name__ == "__main__": raise SystemExit(main())
