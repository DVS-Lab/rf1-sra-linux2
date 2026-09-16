#!/usr/bin/env python3
"""Read-only raw-series/behavior inventory for three Shared Reward source cases.

No data or eligibility is changed. Exact source metadata stays in ignored work/;
stdout contains only a redacted review report, suitable for run_logged.sh.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
SUBJECTS = ("10668", "11913", "11923")
TAGS = ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID", "PatientID",
        "FrameOfReferenceUID",
        "StudyDate", "SeriesDate", "SeriesTime", "AcquisitionDate",
        "AcquisitionTime", "AcquisitionDateTime", "SeriesNumber",
        "SeriesDescription", "ProtocolName", "ImageType", "EchoNumbers",
        "EchoTime", "AcquisitionNumber", "TemporalPositionIdentifier",
        "NumberOfFrames", "InstanceNumber")


def label(text):
    text = re.sub(r"[^a-z0-9]", "", text.lower())
    if "shared" in text:
        return "sharedreward"
    for needle, result in (("trust", "trust"), ("ultimatum", "ugr"),
                           ("ugr", "ugr"), ("socialdoorsface", "socialdoors"),
                           ("socialdoorsdoor", "doors"), ("localizer", "localizer"),
                           ("fieldmap", "fieldmap"), ("t1", "anatomical"),
                           ("t2", "anatomical")):
        if needle in text:
            return result
    return "other"


def timestamp(record):
    value = record.get("AcquisitionDateTime", "")
    if not value:
        value = record.get("AcquisitionDate", "") + record.get("AcquisitionTime", "")
    # Only explicit acquisition timestamps are used. No filesystem/commit times
    # or shifted BIDS dates are silently substituted for scanner chronology.
    if not re.fullmatch(r"\d{14}(?:\.\d+)?(?:[+-]\d{4})?", value):
        return ""
    return value


def clock_seconds(value):
    if not value:
        return None
    seconds = re.match(r"\d{2}(?:\.\d+)?", value[12:]).group(0)
    return int(value[8:10]) * 3600 + int(value[10:12]) * 60 + float(seconds)


def read_header(path):
    import pydicom
    with warnings.catch_warnings(record=True) as caught:
        # A malformed-header warning can contain private values. Record a count
        # privately, not the warning text in the public launcher log.
        warnings.simplefilter("always")
        ds = pydicom.dcmread(path, stop_before_pixels=True, specific_tags=TAGS)
        values = {}
        for name in TAGS:
            val = getattr(ds, name, "")
            values[name] = str(val) if name != "ImageType" else [str(x) for x in val]
        if not all(values[k] for k in ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID")):
            raise ValueError("required DICOM identity absent")
    values["warning_count"] = len(caught)
    return values


def collect_series(paths, reader=read_header):
    series, seen, errors = {}, {}, []
    for subject, path in paths:
        try:
            r = reader(path)
            uid = (r["StudyInstanceUID"], r["SeriesInstanceUID"])
            if uid not in series:
                series[uid] = {"study_uid": uid[0], "series_uid": uid[1],
                    "folders": set(), "sample_path": str(path), "headers": 0,
                    "duplicate_files": 0, "fields": {k: set() for k in TAGS
                    if k not in ("SOPInstanceUID", "ImageType")},
                    "warning_count": 0, "image_types": set(), "acquisition_timestamps": set()}
            s = series[uid]
            s["folders"].add(subject)
            s["warning_count"] += r.get("warning_count", 0)
            # Preserve changed registration/timing metadata even in duplicate
            # copies; SOP deduplication is only for instance counting.
            for name in s["fields"]:
                if r.get(name):
                    s["fields"][name].add(r[name])
            s["image_types"].update(r.get("ImageType", []))
            if timestamp(r):
                s["acquisition_timestamps"].add(timestamp(r))
            if r["SOPInstanceUID"] in seen:
                if seen[r["SOPInstanceUID"]] != uid:
                    raise ValueError("SOP identity conflicts with study/series identity")
                s["duplicate_files"] += 1
                continue
            seen[r["SOPInstanceUID"]] = uid
            s["headers"] += 1
        except Exception as exc:
            errors.append({"path": str(path), "error_type": type(exc).__name__})
    return list(series.values()), errors


def serialize(value):
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def event_segments(path):
    raw = path.read_bytes()
    rows = list(csv.reader(raw.decode("utf-8-sig").splitlines()))
    segments, current, header = [], [], None
    for row in rows:
        if not row or not any(row):
            continue
        row = [cell.lstrip("\ufeff") for cell in row]
        if "decision_onset" in row and "Partner" in row:
            if current:
                segments.append(current)
            header, current = row, []
        elif header:
            current.append(dict(zip(header, row)))
    if current:
        segments.append(current)
    result = []
    for segment in segments:
        # Hash timing/condition data only; no friend names, pictures or responses
        # are printed. Relative timing cannot by itself identify a scanner run.
        columns = ("Trialn", "TrialType", "Partner", "Feedback", "ITI", "ISI")
        design = [[r.get(k, "") for k in columns] for r in segment]
        relative = [{k: v for k, v in r.items() if k in columns or
                     k in ("decision_onset", "outcome_onset", "outcome_offset")}
                    for r in segment]
        result.append({"rows": len(segment),
            "design_sha256": hashlib.sha256(json.dumps(design).encode()).hexdigest(),
            "timing_sha256": hashlib.sha256(json.dumps(relative, sort_keys=True).encode()).hexdigest()})
    if not result:
        raise ValueError("no recognizable Shared Reward segments")
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "segments": result}


def public_report(series, bids, events, errors, missing, salt):
    def token(kind, value):
        return kind + hmac.new(salt, value.encode(), hashlib.sha256).hexdigest()[:10]
    origins = {}
    for s in series:
        for t in s["acquisition_timestamps"]:
            origins[t[:8]] = min(origins.get(t[:8], float("inf")), clock_seconds(t))
    lines = ["# Shared Reward source-validity inventory", "",
        "Read-only evidence collection; NOT source-identity or cohort approval.",
        "Raw series are not acquisition counts: echoes, phase/magnitude and SBRefs can be separate series.",
        "Compare complete scanner episodes before assigning behavioral attempts.",
        "Date/UID/patient tokens are comparable only within this report. Exact values stay private.", "",
        f"DICOM series: {len(series)}; unreadable headers: {len(errors)}; header warnings: {sum(s['warning_count'] for s in series)}; missing input groups: {len(missing)}.", "",
        "Relative seconds share a zero within each acquisition-day token, not across days; scanner clocks are not assumed synchronized with task computers.",
        "The timestamp range is the observed header range, not an inferred scan duration.",
        "folder subject | study token | series token | patient token | acquisition day token | series number | task hint | protocol run hint | kind | echoes | unique DICOM instances | duplicate files | relative start/end seconds",
        "---|---|---|---|---|---|---|---|---|---|---|---|---"]
    for s in sorted(series, key=lambda r: (sorted(r["acquisition_timestamps"] or {""})[0], r["series_uid"])):
        f = s["fields"]
        text = " ".join(f["ProtocolName"] | f["SeriesDescription"])
        kind = "SBRef" if "sbref" in text.lower() else "phase" if "P" in s["image_types"] else "magnitude" if "M" in s["image_types"] else "unspecified"
        dates = sorted({t[:8] for t in s["acquisition_timestamps"]})
        # Never echo arbitrary DICOM strings, including protocol/series labels.
        nums = sorted(v for v in f["SeriesNumber"] if re.fullmatch(r"\d+", v))
        echoes = sorted(v for v in f["EchoNumbers"] if re.fullmatch(r"\d+", v))
        protocol_runs = sorted(set(re.findall(r"run[ _-]*(\d+)", text.lower())))
        spans = []
        for day in dates:
            times = [clock_seconds(t) - origins[day] for t in s["acquisition_timestamps"] if t[:8] == day]
            spans.append(f"{token('D', day)}:{min(times):.3f}/{max(times):.3f}")
        lines.append(" | ".join([",".join(sorted(s["folders"])), token("S", s["study_uid"]), token("R", s["series_uid"]),
            ",".join(token("P", x) for x in sorted(f["PatientID"])) or "missing",
            ",".join(token("D", x) for x in dates) or "missing",
            ",".join(nums) or "unknown", label(text), ",".join(protocol_runs) or "unspecified", kind, ",".join(echoes) or "unknown",
            str(s["headers"]), str(s["duplicate_files"]), ";".join(spans) or "missing"]))
    lines += ["", "## BIDS inventory (not independent identity proof)"]
    for subject in SUBJECTS:
        selected = [r for r in bids if r["subject"] == subject]
        runs = sorted({r["run"] for r in selected})
        lines.append(f"sub-{subject}: {len(runs)} Shared Reward run label(s): {','.join(runs) or 'none'}.")
        for r in selected:
            lines.append(f"  run-{r['run']}: volumes={r['volumes']}; TR={r['tr']} seconds.")
    lines += ["", "## Behavioral sources: sub-10668"]
    for e in events:
        # Files selected by a fixed allowlist; filenames contain only study IDs.
        for n, seg in enumerate(e["segments"], 1):
            lines.append(f"{Path(e['path']).name} segment {n}: n={seg['rows']}; design={seg['design_sha256']}; timing={seg['timing_sha256']}")
    lines += ["", "Missing input groups: " + (", ".join(missing) or "none"),
        "Raw acquisition chronology and exact BIDS source metadata are in the private JSON.",
        "BIDS scans.tsv dates can be shifted; do not equate them with raw acquisition dates.",
        "No automatic mapping, source edits, eligibility changes, or QC exclusions performed."]
    return "\n".join(lines) + "\n"


def run(args):
    import nibabel as nib
    import pydicom  # Dependency preflight before producing partial output.
    del pydicom
    private = args.private_output.resolve()
    if not private.is_relative_to((ROOT / "work").resolve()) or private == (ROOT / "work").resolve():
        raise ValueError("private output must be a NEW subdirectory of this repository's ignored work/")
    if private.exists():
        raise ValueError("private output already exists; choose a new audit directory")
    os.umask(0o077)
    private.mkdir(parents=True, mode=0o700)
    paths, missing = [], []
    for subject in SUBJECTS:
        folders = [p for p in args.source_root.iterdir() if p.is_dir() and
                   re.search(rf"(?<!\d){subject}(?!\d)", p.name)]
        files = sorted({p for folder in folders for p in folder.rglob("*")
                        if p.is_file() and p.suffix.lower() in (".dcm", ".ima")})
        if not files:
            missing.append(f"sub-{subject}-DICOMs")
        paths.extend((subject, p) for p in files)
    print(f"Reading {len(paths)} DICOM headers; pixels are not loaded.", flush=True)
    series, errors = collect_series(paths)
    bids, sidecars = [], []
    for subject in SUBJECTS:
        func = args.bids_root / f"sub-{subject}" / "ses-01" / "func"
        images = sorted(func.glob(f"sub-{subject}_ses-01_task-sharedreward_run-*_echo-1_part-mag_bold.nii.gz"))
        if not images:
            missing.append(f"sub-{subject}-BIDS-echo1-magnitude")
        for image in images:
            header = nib.load(image).header
            run_id = re.search(r"_run-(\d+)_", image.name).group(1)
            scale = {"sec": 1, "msec": 0.001, "usec": 0.000001}.get(header.get_xyzt_units()[1])
            bids.append({"subject": subject, "run": run_id,
                         "volumes": int(header.get_data_shape()[3]),
                         "tr": float(header.get_zooms()[3]) * scale if scale else "unknown-unit",
                         "path": str(image)})
            if not image.with_name(image.name.replace(".nii.gz", ".json")).is_file():
                missing.append(f"sub-{subject}-run-{run_id}-BIDS-sidecar")
        # Private only: time fields/identifiers are needed for mapping. Include
        # all tasks for visit chronology, not just Shared Reward.
        for p in sorted(func.glob("*_bold.json")):
            sidecars.append({"path": str(p), "metadata": json.loads(p.read_text())})
    events = []
    for name in ("sub-10668_task-sharedreward_run-1_raw.csv",
                 "sub-10668_task-sharedreward_run-2_raw.csv",
                 "sub-10668_task-sharedreward_run-1_raw.csv~"):
        p = args.behavior_root / "Scan-Card_Guessing_Game/logs/10668" / name
        if p.is_file():
            events.append(event_segments(p))
        else:
            missing.append(name)
    salt = secrets.token_bytes(32)
    inventory = {"collected_utc": datetime.now(timezone.utc).isoformat(),
                 "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 "series": series, "header_errors": errors, "bids": bids,
                 "bids_sidecars": sidecars, "events": events, "missing": missing,
                 "redaction_key_hex": salt.hex()}
    (private / "inventory.json").write_text(json.dumps(inventory, default=serialize, indent=2) + "\n")
    report = public_report(series, bids, events, errors, missing, salt)
    (private / "redacted-report.md").write_text(report)
    print(report)
    print("Private inventory saved under the requested ignored work/ directory; do not git-add it.")
    print("CHECK FAILED: incomplete inventory." if errors or missing else
          "CHECK PASSED: inventory collected; source-validity decisions remain pending.")
    return 1 if errors or missing else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--bids-root", type=Path, default=ROOT / "bids")
    parser.add_argument("--behavior-root", type=Path, required=True,
                        help="Private rf1-sra/stimuli directory")
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as exc:
        # Do not place private DICOM values or source exception strings in logs.
        print(f"ERROR: audit stopped ({type(exc).__name__}). Check dependencies, input mounts, and a fresh private output path.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
