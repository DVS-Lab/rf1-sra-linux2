#!/usr/bin/env python3
"""Read-only, redacted source-link review of the existing private inventory.

No DICOM rescan, source repair, eligibility change, or participant-identity
approval. A unique metadata candidate is not an exact source-series link.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = (("10668", "1"), ("11913", "1"), ("11913", "2"),
            ("11923", "1"), ("11923", "2"))
CONSTRAINTS = ("SeriesNumber", "ProtocolName", "SeriesDescription")


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


def review(inventory, bids_root):
    lines = ["# Shared Reward saved-inventory source-link review", "",
             "Read-only metadata linkage, NOT source-validity or participant-identity approval.",
             "Only unchanged live BIDS sidecars are compared with the saved inventory.",
             "No shifted BIDS dates, commit times, durations, or behavioral quality are used to assign sources.",
             "", "subject | run | status | source candidates | conflicting fields",
             "---|---|---|---|---"]
    rows = []
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
        rows.append((subject, run, status, candidates, bad))
    linked_uids = [candidates[0]["series_uid"] for _, _, status, candidates, _ in rows
                   if status == "UID_LINKED"]
    unresolved = 0
    for subject, run, status, candidates, bad in rows:
        if status == "UID_LINKED" and linked_uids.count(candidates[0]["series_uid"]) > 1:
            status = "SOURCE_REUSED"
        unresolved += status != "UID_LINKED"
        lines.append(f"{subject} | {run} | {status} | " +
                     " / ".join(safe_series(s) for s in candidates) +
                     " | " + ",".join(bad))
    incomplete = bool(inventory["header_errors"] or inventory["missing"])
    lines += ["", f"Exact UID links: {len(EXPECTED) - unresolved}/{len(EXPECTED)}.",
              f"Saved inventory incomplete: {'yes' if incomplete else 'no'}.",
              "CANDIDATE_ONLY needs independent conversion provenance; series numbers and protocol labels are not globally unique.",
              "An exact UID link identifies scanner series, not whether the correct participant was registered.",
              "10668 behavioral synchronization and 10657 run-2 name correction remain separate human facts.",
              "The historical 11913/11923 note is not adjudicated automatically by this report.",
              "No files, mappings, eligibility, or QC policy were changed."]
    return "\n".join(lines) + "\n", int(bool(unresolved or incomplete))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--bids-root", type=Path, default=ROOT / "bids")
    args = parser.parse_args(argv)
    try:
        raw = args.inventory.read_bytes()
        report, result = review(json.loads(raw), args.bids_root)
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
