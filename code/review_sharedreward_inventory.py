#!/usr/bin/env python3
"""Read-only, redacted source-link review of the existing private inventory.

No DICOM rescan, source repair, eligibility change, or participant-identity
approval. A unique metadata candidate is not an exact source-series link.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = (("10668", "1"), ("11913", "1"), ("11913", "2"),
            ("11923", "1"), ("11923", "2"))
CONSTRAINTS = ("SeriesNumber", "ProtocolName", "SeriesDescription")
LINKED = {"UID_LINKED", "PROVENANCE_UID_LINKED"}


def stem(subject, run):
    return (f"sub-{subject}_ses-01_task-sharedreward_run-{run}"
            "_echo-1_part-mag_bold")


def conflicts(metadata, series):
    """Compare only shared fields; absent fields supply no evidence."""
    result = []
    fields = series["fields"]
    for name in (*CONSTRAINTS, "StudyInstanceUID"):
        if metadata.get(name) is not None and fields.get(name):
            if str(metadata[name]) not in fields[name]:
                result.append(name)
    image_types = set(metadata.get("ImageType", [])) & {"M", "P"}
    if image_types and not image_types.issubset(set(series["image_types"])):
        result.append("ImageType")
    return result


def source_match(metadata, series):
    uid = metadata.get("SeriesInstanceUID")
    if uid:
        candidates = [s for s in series if s["series_uid"] == uid]
        if not candidates:
            return "UID_NOT_FOUND", [], []
        if len(candidates) != 1:
            return "AMBIGUOUS_UID", candidates, []
        bad = conflicts(metadata, candidates[0])
        return ("METADATA_CONFLICT" if bad else "UID_LINKED"), candidates, bad
    # Search ALL inventoried folders. Restricting to the purported participant
    # would make a source-identity check circular. Never promote a lone candidate.
    available = [name for name in CONSTRAINTS if metadata.get(name) is not None]
    if not available:
        return "NO_SOURCE_KEYS", [], []
    candidates = [s for s in series if not conflicts(metadata, s) and
                  all(s["fields"].get(name) for name in available)]
    status = "CANDIDATE_ONLY" if len(candidates) == 1 else (
        "AMBIGUOUS_CANDIDATES" if candidates else "NO_CANDIDATE")
    return status, candidates, []


def safe_series(series):
    fields = series["fields"]
    numbers = [str(x) for x in fields.get("SeriesNumber", [])
               if re.fullmatch(r"\d+", str(x))]
    folders = [x for x in series["folders"] if x in {"10668", "11913", "11923"}]
    return "folders=" + ",".join(sorted(folders)) + ";series=" + ",".join(sorted(numbers))


def conversion_match(bids_root, subject, run, metadata, series, task="sharedreward", output_stem=None):
    """Follow the saved edit table, not today's heuristic or list ordering guesses.

    HeuDiConv 1.4.0 conversion_info uses the outer item's one-based position
    as `item`; echoes are added to output names later by the converter.
    Parse literal records only: never import/execute the saved heuristic.
    """
    info = bids_root / ".heudiconv" / subject / "ses-01" / "info"
    files = {"edit": info / f"{subject}_ses-01.edit.txt",
             "seqinfo": info / "dicominfo_ses-01.tsv",
             "filegroup": info / "filegroup_ses-01.json"}
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest()
              for name, path in files.items() if path.is_file()}
    if len(hashes) != len(files):
        return "PROVENANCE_MISSING", [], [], hashes
    try:
        table = ast.literal_eval(files["edit"].read_text())
        filegroup = json.loads(files["filegroup"].read_text())
        with files["seqinfo"].open(newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if not {"series_id", "series_uid"}.issubset(reader.fieldnames or []):
                return "PROVENANCE_COLUMNS_MISSING", [], [], hashes
            seqinfo = list(reader)
        expected = f"sub-{subject}/ses-01/func/" + (output_stem or
                    stem(subject, run).replace("task-sharedreward", f"task-{task}"))
        prefixes = {expected, re.sub(r"_echo-\d+(?=_)", "", expected)}
        if expected.endswith("_sbref"):
            prefixes |= {re.sub(r"_part-(mag|phase)(?=_sbref$)", "", p) for p in list(prefixes)}
        selected = []
        for key, items in table.items():
            if not isinstance(key, tuple) or len(key) < 2:
                raise ValueError("unsupported conversion key")
            template, outtypes = key[:2]
            if f"task-{task}_" not in template or "nii.gz" not in outtypes:
                continue
            for index, group in enumerate(items, 1):
                group = group if isinstance(group, list) else [group]
                for subindex, item in enumerate(group, 1):
                    parameters = dict(item) if isinstance(item, dict) else {}
                    seqid = parameters.pop("item") if parameters else item
                    parameters.update(item=index, subject=subject, seqitem=seqid,
                                      subindex=subindex, session="ses-01",
                                      bids_subject_session_prefix=f"sub-{subject}_ses-01",
                                      bids_subject_session_dir=f"sub-{subject}/ses-01")
                    if template.format(**parameters) in prefixes:
                        selected.append(str(seqid))
        if len(selected) != 1:
            return "PROVENANCE_OUTPUT_NOT_UNIQUE", [], [], hashes
        seqid = selected[0]
        rows = [r for r in seqinfo if r["series_id"] == seqid]
        if len(rows) != 1 or rows[0]["series_uid"] in ("", "None", "n/a"):
            return "PROVENANCE_SEQUENCE_NOT_UNIQUE", [], [], hashes
        group = filegroup.get(seqid)
        if not isinstance(group, list) or not group or not all(isinstance(p, str) for p in group):
            return "PROVENANCE_FILEGROUP_MISSING", [], [], hashes
        count = rows[0].get("series_files")
        if count and int(count) != len(group):
            return "PROVENANCE_FILECOUNT_CONFLICT", [], [], hashes
        uid = rows[0]["series_uid"]
        if metadata.get("SeriesInstanceUID") and metadata["SeriesInstanceUID"] != uid:
            return "PROVENANCE_SIDECAR_UID_CONFLICT", [], [], hashes
        status, matches, bad = source_match({**metadata, "SeriesInstanceUID": uid}, series)
        if status == "UID_LINKED":
            # Identity-bearing conversion metadata must agree with the raw
            # inventory too. Do not publish any of the compared values.
            for seqkey, rawkey in (("patient_id", "PatientID"),
                                   ("protocol_name", "ProtocolName"),
                                   ("series_description", "SeriesDescription")):
                value = rows[0].get(seqkey)
                values = matches[0]["fields"].get(rawkey, [])
                if value and values and value not in values:
                    bad.append(rawkey)
            status = "PROVENANCE_METADATA_CONFLICT" if bad else "PROVENANCE_UID_LINKED"
        return status, matches, bad, hashes
    except (ValueError, SyntaxError, TypeError, KeyError, AttributeError):
        return "PROVENANCE_INVALID", [], [], hashes


def review(inventory, bids_root, use_conversion_provenance=False):
    lines = ["# Shared Reward saved-inventory source-link review", "",
             "Read-only metadata linkage, NOT source-validity or participant-identity approval.",
             "Only unchanged live BIDS sidecars are compared with the saved inventory.",
             "No shifted BIDS dates, commit times, durations, or behavioral quality are used to assign sources.",
             "", "subject | run | status | source candidates | conflicting fields",
             "---|---|---|---|---"]
    rows, provenance = [], {}
    for subject, run in EXPECTED:
        name = stem(subject, run)
        saved = [row for row in inventory["bids_sidecars"]
                 if Path(row["path"]).name == name + ".json"]
        func = bids_root / f"sub-{subject}" / "ses-01" / "func"
        path = func / (name + ".json")
        candidates, bad = [], []
        if len(saved) != 1:
            status = "MISSING_OR_DUPLICATE_SNAPSHOT"
        elif not path.is_file() or not (func / (name + ".nii.gz")).is_file():
            status = "LIVE_INPUT_MISSING"
        else:
            metadata = json.loads(path.read_text())
            if metadata != saved[0]["metadata"]:
                status = "SIDECAR_CHANGED"
            else:
                status, candidates, bad = source_match(metadata, inventory["series"])
                if use_conversion_provenance:
                    status, candidates, bad, hashes = conversion_match(
                        bids_root, subject, run, metadata, inventory["series"])
                    provenance[subject] = hashes
        rows.append((subject, run, status, candidates, bad))
    linked_uids = [candidates[0]["series_uid"] for _, _, status, candidates, _ in rows
                   if status in LINKED]
    unresolved = 0
    for subject, run, status, candidates, bad in rows:
        if status in LINKED and linked_uids.count(candidates[0]["series_uid"]) > 1:
            status = "SOURCE_REUSED"
        unresolved += status not in LINKED
        lines.append(f"{subject} | {run} | {status} | " +
                     " / ".join(safe_series(s) for s in candidates) +
                     " | " + ",".join(bad))
    if provenance:
        lines += ["", "## Conversion-record SHA256 (raw content stays private)"]
        for subject, hashes in sorted(provenance.items()):
            lines += [f"sub-{subject} {kind}: {digest}" for kind, digest in sorted(hashes.items())]
    incomplete = bool(inventory["header_errors"] or inventory["missing"])
    lines += ["", f"Exact UID links: {len(EXPECTED) - unresolved}/{len(EXPECTED)}.",
              f"Saved inventory incomplete: {'yes' if incomplete else 'no'}.",
              "CANDIDATE_ONLY needs independent conversion provenance; series numbers and protocol labels are not globally unique.",
              "PROVENANCE_UID_LINKED follows saved edit-table output -> seqinfo UID -> raw inventory, with a populated filegroup and unchanged sidecar.",
              "This validates recorded conversion provenance, not NIfTI pixel identity or correctness of historical scanner registration.",
              "An exact UID link identifies scanner series, not whether the correct participant was registered.",
              "10668 behavioral synchronization and 10657 run-2 name correction remain separate human facts.",
              "The historical 11913/11923 note is not adjudicated automatically by this report.",
              "No files, mappings, eligibility, or QC policy were changed."]
    return "\n".join(lines) + "\n", int(bool(unresolved or incomplete))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--bids-root", type=Path, default=ROOT / "bids")
    parser.add_argument("--conversion-provenance", action="store_true",
                        help="Also follow saved HeuDiConv edit/seqinfo/filegroup records")
    args = parser.parse_args(argv)
    try:
        raw = args.inventory.read_bytes()
        report, result = review(json.loads(raw), args.bids_root, args.conversion_provenance)
        print("Inventory SHA256: " + hashlib.sha256(raw).hexdigest())
        print(report, end="")
        print("REVIEW REQUIRED: source-link evidence incomplete." if result else
              "LINK CHECK PASSED: metadata links only; source-validity closeouts remain pending.")
        return result
    except Exception as exc:
        # JSON/path/metadata exceptions can include identifying source values.
        print(f"ERROR: saved-inventory review stopped ({type(exc).__name__}); inspect inputs privately.",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
