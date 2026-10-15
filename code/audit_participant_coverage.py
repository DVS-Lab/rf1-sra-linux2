#!/usr/bin/env python3
"""Read-only participant/source reconciliation; per-ID results stay private."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from participants import exclusions, read_tsv, source_row

ROOT = Path(__file__).resolve().parents[1]
REQUESTED = """10847 10861 10867 10874 10878 10885 11077 11079 11144 11146
11206 11207 11213 11217 11228 11381 11442 11449 11475 11552 11562 11593
11603 11753 11836 11837 11852 11856 11892 11905 11915 11919 12028""".split()


def fail_walk(error):
    raise error


def index_sources(root):
    result = defaultdict(list)
    unmatched = 0
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        match = re.fullmatch(r"(?:Smith-SRA-)?(\d{5})(?:[-_].*)?", path.name)
        if match:
            result[match[1]].append(path)
        else:
            unmatched += 1
    return result, unmatched


def files_under(root):
    if not root.exists():
        return
    # Permission errors are not interpreted as absent data. Do not follow
    # directory symlinks silently; report them for private path review instead.
    for parent, dirs, files in os.walk(root, onerror=fail_walk):
        if any((Path(parent) / name).is_symlink() for name in dirs):
            raise ValueError("directory symlink requires path review")
        for name in files:
            yield Path(parent) / name


def raw_evidence(folders):
    counts = Counter()
    for folder in folders:
        for path in files_under(folder):
            if path.suffix.lower() in {".dcm", ".ima"}:
                counts["dicom_files"] += 1
                label = str(path.parent.relative_to(folder)).lower()
                if "localizer" in label or "scout" in label:
                    counts["localizer_path_files"] += 1
            elif path.suffix.lower() in {".zip", ".tar", ".gz"}:
                counts["archive_files"] += 1
    return dict(counts)


def classify(row):
    if row["source_excluded"]:
        return "excluded_but_in_table" if row["table_rows"] else "intentional_source_exclusion"
    if row["table_rows"] > 1:
        return "duplicate_table_rows"
    if row["table_rows"]:
        return "represented" if row["baseline_source"] == "available" else "represented_source_review"
    if row["bids_images"]:
        return "bids_missing_participant_row"
    if row["derivative_images"]:
        return "derivatives_without_bids_review"
    if row["production_raw"].get("dicom_files", 0):
        return "raw_present_conversion_review"
    if row["source_folders"]:
        return "source_folder_without_recognized_dicoms"
    if row["seqinfo_files"]:
        return "conversion_inventory_without_images"
    return "no_local_imaging_evidence"


def collect(project, source, excluded_root):
    bids = project / "bids"
    derivatives = project / "derivatives"
    for root in (bids, source, excluded_root, derivatives):
        if not root.is_dir():
            raise ValueError("required root unavailable")
    fields, rows, table_sha = read_tsv(bids / "participants.tsv")
    if "participant_id" not in fields:
        raise ValueError("participant_id missing")
    table_counts = Counter()
    for row in rows:
        if not re.fullmatch(r"sub-\d{5}", row["participant_id"]):
            raise ValueError("invalid participant ID")
        table_counts[row["participant_id"][4:]] += 1
    excluded = {s[4:] for s in exclusions(excluded_root)}
    source_index, unmatched = index_sources(source)
    excluded_index, excluded_unmatched = index_sources(excluded_root)
    image_index = defaultdict(Counter)
    seqinfos = defaultdict(list)
    for path in files_under(bids):
        rel = path.relative_to(bids)
        if re.fullmatch(r"sub-\d{5}", rel.parts[0]) and path.name.endswith((".nii", ".nii.gz")):
            image_index[rel.parts[0][4:]]["bids_images"] += 1
        if len(rel.parts) > 2 and rel.parts[0] == ".heudiconv" and re.fullmatch(r"\d{5}", rel.parts[1]):
            if path.name.startswith("dicominfo") and path.suffix == ".tsv":
                seqinfos[rel.parts[1]].append(str(rel))
    # Production derivatives only, never retired repairs/backups or scratch.
    for stage in ("fmriprep", "mriqc", "tedana", "warpkit"):
        for path in files_under(derivatives / stage):
            rel = path.relative_to(derivatives / stage)
            if re.fullmatch(r"sub-\d{5}", rel.parts[0]) and path.name.endswith((".nii", ".nii.gz")):
                image_index[rel.parts[0][4:]]["derivative_images"] += 1
    bids_ids = {p.name[4:] for p in bids.iterdir() if p.is_dir() and re.fullmatch(r"sub-\d{5}", p.name)}
    subjects = sorted(set(REQUESTED) | set(table_counts) | set(source_index) |
                      set(excluded_index) | set(image_index) | set(seqinfos) | bids_ids)
    result = []
    for index, sub in enumerate(subjects, 1):
        baseline = bids / ".heudiconv" / sub / "ses-01/info/dicominfo_ses-01.tsv"
        baseline_status = "absent"
        if baseline.exists():
            try:
                values, _ = source_row(baseline, sub)
                baseline_status = "available" if values["age"] != "n/a" and values["sex"] != "n/a" else "missing_values"
            except ValueError:
                baseline_status = "invalid_or_conflicting"
        item = dict(subject=sub, requested=sub in REQUESTED, table_rows=table_counts[sub],
                    source_excluded=sub in excluded, source_folders=[str(p) for p in source_index[sub]],
                    excluded_folders=[str(p) for p in excluded_index[sub]],
                    production_raw=raw_evidence(source_index[sub]),
                    excluded_raw=raw_evidence(excluded_index[sub]),
                    bids_images=image_index[sub]["bids_images"],
                    derivative_images=image_index[sub]["derivative_images"],
                    seqinfo_files=seqinfos[sub], baseline_source=baseline_status)
        item["status"] = classify(item)
        result.append(item)
        if index % 50 == 0:
            print(f"Inspected {index}/{len(subjects)} participant trees", flush=True)
    return dict(schema_version=1, participants_sha256=table_sha,
                roots=dict(project=str(project.resolve()), source=str(source.resolve()), exclusions=str(excluded_root.resolve())),
                scope="requested IDs plus discovered local production subjects",
                unmatched_source_directories=unmatched, unmatched_exclusion_directories=excluded_unmatched,
                subjects=result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra"))
    parser.add_argument("--exclusions-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.private_dir.resolve()
    work = (args.project_root / "work").resolve()
    if output == work or work not in output.parents:
        raise ValueError("private output must be a new directory under ignored work/")
    if output.exists():
        raise ValueError("output already exists; use a new timestamp")
    print("Enumerating source, BIDS and active derivative evidence; no inputs will be changed.", flush=True)
    report = collect(args.project_root, args.source_root, args.exclusions_root)
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    report["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (output / "inventory.json").write_text(json.dumps(report, indent=2) + "\n")
    columns = ["subject", "requested", "status", "table_rows", "bids_images", "derivative_images", "baseline_source"]
    with (output / "review.tsv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["subjects"])
    for title, selected in (("Jacob's 33", [r for r in report["subjects"] if r["requested"]]),
                            ("All discovered", report["subjects"])):
        print(f"{title}: {len(selected)} participants")
        for status, count in sorted(Counter(r["status"] for r in selected).items()):
            print(f"  {status}: {count}")
    print(f"Unmatched production/exclusion directories: {report['unmatched_source_directories']}/{report['unmatched_exclusion_directories']}")
    print("Private per-ID evidence: work/<requested-directory>/review.tsv and inventory.json")
    print("AUDIT COMPLETE: no inputs changed; categories require review, not automatic eligibility decisions.")
    print("DICOM counts are filename evidence, not usable-scan validation. No local evidence does not prove never scanned.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"AUDIT FAILED ({type(exc).__name__}): inspect roots/permissions privately; do not infer absent data.", file=sys.stderr)
        sys.exit(1)
