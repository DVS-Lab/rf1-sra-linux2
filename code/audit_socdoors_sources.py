#!/usr/bin/env python3
"""Read-only follow-up for the eleven participants absent from Doors imaging.

Reads all saved series labels, current behavioral sources, and all DICOM headers
for 11171/11203. Does not convert data or decide exclusions/recoverability.
Only allowlisted summaries reach stdout; exact metadata stays in ignored work/.
Use run_logged.sh --include-full-log. --behavior-only supports a local checkout.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import warnings

from convert_behavior import convert_source, resolve_sources

ROOT = Path(__file__).resolve().parents[1]
SUBJECTS = "11083 11085 11110 11128 11145 11171 11203 11317 11364 11396 11443".split()
HEADER_SUBJECTS = {"11171", "11203"}
TAGS = ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID", "SeriesNumber",
        "ProtocolName", "SeriesDescription", "ImageType", "EchoNumbers", "EchoTime",
        "InstanceNumber", "AcquisitionNumber", "TemporalPositionIdentifier",
        "NumberOfTemporalPositions", "NumberOfFrames", "RepetitionTime")


def hint(text):
    """Return fixed vocabulary, never arbitrary source labels."""
    text = re.sub(r"[^a-z0-9]", "", text.lower())
    for needle, value in (("socialdoorsface", "socialdoors"),
                          ("socialdoorsdoor", "doors"), ("shared", "sharedreward"),
                          ("trust", "trust"), ("ugr", "ugr"), ("ultimatum", "ugr"),
                          ("localizer", "localizer"), ("phoenix", "scanner-report"),
                          ("field", "fieldmap"), ("diff", "diffusion"),
                          ("dwi", "diffusion"), ("hydi", "diffusion"),
                          ("t1", "anatomical"), ("t2", "anatomical")):
        if needle in text:
            return value
    return "doors-like-unspecified" if "door" in text or "srsocial" in text else "other"


def numeric(value):
    value = str(value)
    return value if re.fullmatch(r"\d+(?:\.\d+)?", value) else "unknown"


def series_number(value):
    match = re.match(r"(\d+)(?:-|$)", str(value))
    return match.group(1) if match else "unknown"


def behavioral_report(root):
    records, failures = [], 0
    print("\n## Behavioral sources (not proof of corresponding MRI acquisition)")
    print("subject | session | task | source status | trials | missed | last event end (s)")
    print("---|---|---|---|---|---|---")
    for sub in SUBJECTS:
        for ses in ("01", "02"):
            for task in ("doors", "socialdoors"):
                record = dict(subject=sub, session=ses, task=task)
                try:
                    resolved = resolve_sources(root, sub, ses, task, [1])[1]
                    record.update(status=resolved.status, detail=resolved.detail)
                    if resolved.path:
                        converted = convert_source(task, resolved.path)
                        record.update(path=str(resolved.path), sha256=converted.source_sha256,
                            trials=converted.trial_count,
                            missed=sum(r["trial_type"] == "decision-missed" for r in converted.rows),
                            last_end=max(float(r["onset"]) + float(r["duration"]) for r in converted.rows))
                except Exception as exc:
                    record.update(status="error", error_type=type(exc).__name__)
                    failures += 1
                records.append(record)
                end = f"{record['last_end']:.3f}" if "last_end" in record else "-"
                print(f"{sub} | {ses} | {task} | {record['status']} | "
                      f"{record.get('trials', '-')} | {record.get('missed', '-')} | {end}")
    return records, failures


def read_header(path):
    import pydicom
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ds = pydicom.dcmread(path, stop_before_pixels=True, specific_tags=TAGS)
        values = {key: str(getattr(ds, key, "")) for key in TAGS}
        values["ImageType"] = [str(v) for v in getattr(ds, "ImageType", [])]
    if not all(values[k] for k in ("StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID")):
        raise ValueError("DICOM identity missing")
    return values, len(caught)


def collect_headers(paths, reader=read_header):
    groups, seen, errors = {}, {}, []
    for path in paths:
        try:
            row, warning_count = reader(path)
            key = (row["StudyInstanceUID"], row["SeriesInstanceUID"])
            if key not in groups:
                groups[key] = dict(fields=defaultdict(set), echoes=Counter(), frames=Counter(),
                                   duplicates=0, warnings=0, positions=defaultdict(set))
            group = groups[key]
            group["warnings"] += warning_count
            for field in TAGS:
                if field != "SOPInstanceUID":
                    values = row[field] if field == "ImageType" else [row[field]]
                    group["fields"][field].update(v for v in values if v)
            sop = row["SOPInstanceUID"]
            if sop in seen:
                if seen[sop] != key:
                    raise ValueError("SOP identity conflict")
                group["duplicates"] += 1
                continue
            seen[sop] = key
            echo = row["EchoNumbers"] or "missing"
            group["echoes"][echo] += 1
            group["frames"][row["NumberOfFrames"] or "absent"] += 1
            position = row["TemporalPositionIdentifier"]
            if position:
                group["positions"][echo].add(position)
        except Exception as exc:
            errors.append(dict(path=str(path), error_type=type(exc).__name__))
    return list(groups.values()), errors


def header_report(sub, groups, errors):
    print(f"\n## sub-{sub}: header-level inventory; {len(errors)} unreadable/conflicting files")
    print("series | task hint | kind | unique instances by echo | temporal positions by echo | frame tags | TR (ms)")
    print("---|---|---|---|---|---|---")
    for group in groups:
        fields = group["fields"]
        text = " ".join(fields["ProtocolName"] | fields["SeriesDescription"])
        kinds = fields["ImageType"]
        kind = "SBRef" if "sbref" in text.lower() else "phase" if "P" in kinds else "magnitude" if "M" in kinds else "unknown"
        number = ",".join(sorted(numeric(v) for v in fields["SeriesNumber"])) or "unknown"
        echoes = ",".join(f"{numeric(k)}:{v}" for k, v in sorted(group["echoes"].items()))
        positions = ",".join(f"{numeric(k)}:{len(v)}" for k, v in sorted(group["positions"].items())) or "unavailable"
        frames = ",".join(f"{'absent' if k == 'absent' else numeric(k)}:{v}" for k, v in sorted(group["frames"].items()))
        tr = ",".join(sorted(numeric(v) for v in fields["RepetitionTime"])) or "unknown"
        print(f"{number} | {hint(text)} | {kind} | {echoes} | {positions} | {frames} | {tr}")
    print(f"Duplicate copies: {sum(g['duplicates'] for g in groups)}; header warnings: {sum(g['warnings'] for g in groups)}")
    print("Instance/echo counts are NOT volume counts. Enhanced multiframe headers may lack per-frame echo/position tags.")
    print("Matching counts alone do not prove complete, correctly paired magnitude/phase acquisitions.")


def run(args):
    if not args.behavior_root.is_dir():
        raise ValueError("Behavior root unavailable")
    if not args.behavior_only:
        import pydicom  # Preflight before creating output.
        if not args.source_root.is_dir() or not (ROOT / "bids").is_dir():
            raise ValueError("Source or BIDS root unavailable")
    private = args.private_output.resolve()
    work = (ROOT / "work").resolve()
    if not private.is_relative_to(work) or private == work or private.exists():
        raise ValueError("Private output must be a new subdirectory of ignored work/")
    os.umask(0o077)
    private.mkdir(parents=True, mode=0o700)
    inventory = {"script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    print("# Missing Doors follow-up: read-only evidence, not recovery approval")
    inventory["behavior"], failures = behavioral_report(args.behavior_root)
    if args.behavior_only:
        print("\nBEHAVIOR-ONLY: no source DICOMs, saved series inventories, or session notes checked.")
    else:
        inventory["subjects"] = {}
        for sub in SUBJECTS:
            record = dict(seqinfo=[], source_folders=[], headers=[], errors=[])
            inventory["subjects"][sub] = record
            print(f"\n## sub-{sub}: all saved series, including non-Doors labels")
            tables = sorted((ROOT / "bids/.heudiconv" / sub).rglob("dicominfo*.tsv"))
            if not tables:
                print("MISSING saved conversion inventory")
                failures += 1
            for table in tables:
                with table.open(newline="") as f:
                    rows = list(csv.DictReader(f, delimiter="\t"))
                record["seqinfo"].append(dict(path=str(table), rows=rows))
                session = next((v for v in table.parts if re.fullmatch(r"ses-\d+", v)), "unknown")
                print(f"{session}: {len(rows)} series; series / hint / dim4 / RF1-label / XA30-label")
                for row in rows:
                    protocol, desc = row.get("protocol_name", ""), row.get("series_description", "")
                    tokens = ("SocialDoors_doors", "SocialDoors_face")
                    print(f"{series_number(row.get('series_id', ''))} / {hint(protocol + ' ' + desc)} / "
                          f"{numeric(row.get('dim4', ''))} / {any(t in protocol for t in tokens)} / {any(t in desc for t in tokens)}")
            folders = sorted(p for p in args.source_root.iterdir() if p.is_dir() and
                             re.search(rf"(?<!\d){sub}(?!\d)", p.name))
            record["source_folders"] = list(map(str, folders))
            print(f"Matching source folders: {len(folders)} (not an archive-wide search)")
            if not folders:
                failures += 1
            if sub in HEADER_SUBJECTS:
                paths = sorted({p for folder in folders for p in folder.rglob("*")
                                if p.is_file() and p.suffix.lower() in {".dcm", ".ima"}})
                print(f"Reading {len(paths)} headers, no pixels.", flush=True)
                groups, errors = collect_headers(paths)
                record.update(headers=groups, errors=errors)
                header_report(sub, groups, errors)
                failures += len(errors) + (not paths)
    def serialize(value):
        if isinstance(value, set):
            return sorted(value)
        raise TypeError(type(value).__name__)
    (private / "inventory.json").write_text(json.dumps(inventory, default=serialize, indent=2) + "\n")
    print("\nExact metadata saved only in ignored work/. Do not commit that directory.")
    print("Session notes were not located/read by this utility. Behavioral completion does not prove MRI coverage.")
    print("No data, conversions, or exclusions changed.")
    print(f"Collection errors/missing required inputs: {failures}")
    print("CHECK FAILED: incomplete evidence collection." if failures else
          "CHECK PASSED: requested evidence collected; missing-task explanations remain to be reviewed.")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra"))
    parser.add_argument("--behavior-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra/stimuli"))
    parser.add_argument("--private-output", required=True, type=Path)
    parser.add_argument("--behavior-only", action="store_true")
    try:
        return run(parser.parse_args())
    except Exception as exc:
        print(f"ERROR: audit stopped ({type(exc).__name__}); check roots, dependencies, and a fresh private output directory.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
