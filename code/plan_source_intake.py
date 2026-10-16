#!/usr/bin/env python3
"""Fast, read-only session discovery before selecting prepdata inputs.

Stops after finding a DICOM per source tree; does not count the whole cohort,
validate images, infer task identity, select heuristics, or overwrite BIDS.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from make_repair_runlists import source_scan_dir
from participants import exclusions
from source_layout import load_supplemental_sources

ROOT = Path(__file__).resolve().parents[1]


def fail_walk(error):
    raise error


def has_dicom(root):
    if not root.is_dir():
        return False
    for parent, dirs, files in os.walk(root, onerror=fail_walk):
        if any((Path(parent) / name).is_symlink() for name in dirs):
            raise ValueError("source directory symlink needs private review")
        if any(name.endswith(".dcm") for name in files):
            return True
    return False


def collect(project, source, excluded_root, manifest):
    for path in (project / "bids", source, excluded_root):
        if not path.is_dir():
            raise ValueError("required root unavailable")
    excluded = exclusions(excluded_root)
    specs = load_supplemental_sources(manifest)
    supplemental_names = {s.source_relative.parts[0] for s in specs}
    rows, unmatched, omitted = [], [], set()
    for folder in sorted(source.iterdir()):
        if not folder.is_dir():
            continue
        if folder.name in supplemental_names:
            continue
        match = re.fullmatch(r"Smith-SRA-(\d{5})(-2)?", folder.name)
        if folder.name == "11891":
            sub, ses = "11891", "01"
        elif match:
            sub, ses = match[1], "02" if match[2] else "01"
        else:
            unmatched.append(str(folder))
            continue
        if "sub-" + sub in excluded:
            omitted.add(sub)
            continue
        scans = source_scan_dir(source, sub if ses == "01" else sub + "-2")
        target = project / "bids" / f"sub-{sub}" / f"ses-{ses}"
        matching = [s for s in specs if (s.subject, s.session) == (sub, ses)]
        supplemental_ok = all(s.status == "active" and has_dicom(source / s.source_relative / "scans") for s in matching)
        if not supplemental_ok:
            status = "supplemental_review"
        elif not has_dicom(scans):
            status = "source_layout_or_download_review"
        elif target.exists():
            status = "existing_bids_not_revalidated"
        elif ses == "02" and not (project / "bids/.heudiconv" / sub / "ses-01/info/dicominfo_ses-01.tsv").is_file():
            status = "baseline_metadata_needed_first"
        else:
            status = "new_session_candidate"
        rows.append(dict(subject=sub, session=ses, status=status, source=str(scans)))
    seen = {(r["subject"], r["session"]) for r in rows}
    if len(seen) != len(rows):
        raise ValueError("multiple source folder aliases for one session need review")
    orphan_supplemental = [str(source / s.source_relative) for s in specs
                           if (source / s.source_relative).exists()
                           and (s.subject, s.session) not in seen and "sub-" + s.subject not in excluded]
    unknown_exclusions = [str(p) for p in excluded_root.iterdir()
                          if p.is_dir() and not re.fullmatch(r"Smith-SRA-\d{5}", p.name)]
    return dict(schema_version=1, sessions=rows, excluded_production_subjects=len(omitted),
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                roots=dict(project=str(project.resolve()), source=str(source.resolve()), exclusions=str(excluded_root.resolve())),
                unmatched_source_folders=unmatched, unmatched_exclusion_folders=unknown_exclusions,
                supplemental_without_base=orphan_supplemental)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", type=Path, default=ROOT)
    p.add_argument("--source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra"))
    p.add_argument("--exclusions-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    p.add_argument("--manifest", type=Path, default=ROOT / "code/supplemental_sources.tsv")
    p.add_argument("--private-dir", type=Path, required=True)
    args = p.parse_args()
    output, work = args.private_dir.resolve(), (args.project_root / "work").resolve()
    if output.exists() or work not in output.parents:
        raise ValueError("use a new private directory under ignored work/")
    print("Checking session presence and first DICOM evidence; no conversion or overwrite.", flush=True)
    report = collect(args.project_root, args.source_root, args.exclusions_root, args.manifest)
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    (output / "inventory.json").write_text(json.dumps(report, indent=2) + "\n")
    with (output / "sessions.tsv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, ["subject", "session", "status", "source"], delimiter="\t")
        writer.writeheader()
        writer.writerows(report["sessions"])
    for status, count in sorted(Counter(r["status"] for r in report["sessions"]).items()):
        print(f"{status}: {count}")
    print(f"Source-excluded production subjects omitted: {report['excluded_production_subjects']}")
    for key in ("unmatched_source_folders", "unmatched_exclusion_folders", "supplemental_without_base"):
        print(f"{key}: {len(report[key])}; names/paths remain in private inventory")
    print("subject | session | next-step status (existing BIDS sessions omitted below)")
    for row in report["sessions"]:
        if row["status"] != "existing_bids_not_revalidated":
            print(f"{row['subject']} | {row['session']} | {row['status']}")
    print("INTAKE INVENTORY COMPLETE: review candidates before prepdata --dry-run; no automatic processing.")
    print("Existing sessions were not completeness-checked; added scans within them require separate review.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"INTAKE FAILED ({type(exc).__name__}): inspect paths/permissions privately; no conversion performed.", file=sys.stderr)
        sys.exit(1)
