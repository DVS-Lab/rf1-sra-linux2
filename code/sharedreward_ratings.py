#!/usr/bin/env python3
"""Export RF1 Wave 1 post-task Shared Reward ratings and signed model covariates."""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from participants import atomic_write, digest, exclusions, locked


ROOT = Path(__file__).resolve().parents[1]
LOGS = Path("stimuli/Scan-Card_Guessing_Game/logs")
# The last change to a Wave 1 ratings CSV restores the reviewed sub-10803 source.
WAVE1 = "9b9cf69348adcd6ec0b19861b637f1a63d1129cb"
LOCAL_ATTESTATION = ROOT / "qc/participants/20260927T170745Z-4a69542d-build.json"
PARTNERS = {"3": "friend", "2": "stranger", "1": "computer"}
OUTCOMES = {"0": "win", "1": "loss"}
CELLS = [f"{p}_{o}" for p in PARTNERS.values() for o in OUTCOMES.values()]
ITEMS = ("trial_number", "partner", "rating_dimension", "response")
SUFFIX = "task-sharedreward_acq-post_beh"
NA = "n/a"
SOURCE_FIELDS = ("source_participant_id", "source_file", "source_sha256", "block",
                 "n_items", "n_responses", "selection", "bids_file")


def tsv(fields, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def as_json(data):
    return (json.dumps(data, indent=2) + "\n").encode()


def id_table(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if "participant_id" not in (reader.fieldnames or []):
            raise ValueError(f"Missing participant_id in {path}")
        ids = [r["participant_id"] for r in reader]
    if any(not re.fullmatch(r"sub-\d{5}", s) for s in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"Invalid or duplicate participant IDs in {path}")
    return set(ids)


def study_roster(bids, args):
    table = bids / "participants.tsv"
    roster = id_table(table)
    if not roster:
        raise ValueError("Empty BIDS participants.tsv")
    if args.local_snapshot:
        proof = json.loads(LOCAL_ATTESTATION.read_bytes())
        omitted = id_table(ROOT / "qc/trust_analysis/source_exclusions.tsv")
        if (proof["status"] != "passed" or proof["participants_sha256"] != digest(table.read_bytes())
                or proof["source_exclusion_ids_sha256"] != digest("\n".join(sorted(omitted)).encode())):
            raise ValueError("The local snapshots differ from the verified Linux2 participant build")
    else:
        omitted = exclusions(args.exclusions_root)
    if roster & omitted:
        raise ValueError("The participant roster overlaps current source exclusions. Refresh participants.tsv.")
    return roster, omitted


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *map(str, args)])


def sources(repo, ref, omitted):
    commit = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
    paths = git(repo, "ls-tree", "-r", "--name-only", "-z", commit, "--", LOGS).decode().split("\0")
    candidates = defaultdict(list)
    for name in filter(None, paths):
        path = Path(name)
        parent = path.parent.name.removeprefix("sub-")
        if (not re.fullmatch(r"\d{5}", parent) or "sub-" + parent in omitted
                or "ratings" not in path.name.casefold() or path.suffix.lower() != ".csv"):
            continue
        if (path.parent.parent != LOGS or
                not re.fullmatch(rf"sub-?{parent}_SR-Ratings-[12]?\.csv", path.name)):
            raise ValueError(f"Unrecognized ratings source name in the selected revision: {path}")
        candidates["sub-" + parent].append(name)
    names = [name for files in candidates.values() for name in files]
    if not names:
        raise ValueError("No RF1 ratings sources found in the selected Git revision")
    # Read the archived bytes at this commit, including when the checkout is at another revision.
    packed = git(repo, "archive", "--format=zip", commit, "--", *names)
    with zipfile.ZipFile(io.BytesIO(packed)) as archive:
        contents = {name: archive.read(name) for name in names}
    return commit, candidates, contents


def whole_number(token):
    number = float(token)
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f"Expected an integer, got {token!r}")
    return int(number)


def read_attempts(data):
    """Keep explicit acquisition blocks and the observed item order."""
    blocks = []
    header = None
    for raw in csv.reader(io.StringIO(data.decode("utf-8-sig"), newline="")):
        row = [s.strip().lstrip("\ufeff") for s in raw]
        if not any(row):
            continue
        fields = [s.casefold() for s in row]
        if {"trialnumber", "partner", "trait", "rating"} <= set(fields):
            if len(fields) != len(set(fields)):
                raise ValueError("Duplicate fields in a ratings header")
            header = fields
            blocks.append([])
            continue
        if header is None or len(row) != len(header):
            raise ValueError("Ratings row does not match the acquisition header")
        record = dict(zip(header, row))
        trial = whole_number(record["trialnumber"])
        partner = PARTNERS[record["partner"]]
        outcome = OUTCOMES[record["trait"]]
        attempt = blocks[-1]
        if trial != len(attempt) + 1:
            raise ValueError("Unexpected trial order within a ratings attempt")
        if any((item["partner"], item["rating_dimension"]) == (partner, outcome) for item in attempt):
            raise ValueError("Repeated partner/outcome within a ratings attempt")
        token = record["rating"]
        value = NA if token.casefold() in {"", "none", "nan", "n/a"} else whole_number(token)
        if value != NA and not -5 <= value <= 5:
            raise ValueError("Response outside the acquired -5 to +5 scale")
        attempt.append(dict(trial_number=trial, partner=partner, rating_dimension=outcome, response=value))
    return blocks


def select_file(pid, files):
    if len(files) == 1:
        return files[0]
    # Explicit post-task selection in the reviewed RF1 source-resolution table.
    if pid == "sub-10369" and {Path(f).name for f in files} == {
            "sub10369_SR-Ratings-1.csv", "sub10369_SR-Ratings-2.csv"}:
        return next(f for f in files if f.endswith("-2.csv"))
    raise ValueError(f"Multiple ratings files require an acquisition decision for {pid}")


def selected_block(blocks):
    complete = [i for i, block in enumerate(blocks)
                if len(block) == 6 and all(item["response"] != NA for item in block)]
    populated = [i for i, block in enumerate(blocks) if block]
    candidates = complete or populated
    return candidates[-1] if candidates else None


def model_row(pid, items, has_source):
    values = dict.fromkeys(CELLS, NA)
    for item in items:
        values[f'{item["partner"]}_{item["rating_dimension"]}'] = item["response"]
    count = sum(value != NA for value in values.values())
    status = ("missing_source" if not has_source else "complete" if count == 6
              else "partial" if items else "empty_source")
    reasons = []
    if status != "complete":
        reasons.append(status)
    elif len(set(values.values())) == 1:
        reasons.append("all_six_identical")
    else:
        reasons.extend(f"{p}_loss_gt_win" for p in PARTNERS.values() if values[p + "_loss"] > values[p + "_win"])

    def difference(a, b):
        return NA if NA in (a, b) else a - b

    gaps = {p: difference(values[p + "_win"], values[p + "_loss"]) for p in PARTNERS.values()}
    return dict(participant_id=pid, session_id="ses-01", ratings_status=status, n_responses=count,
                **values, **{p + "_win_minus_loss": gap for p, gap in gaps.items()},
                X_FS=difference(gaps["friend"], gaps["stranger"]),
                X_FC=difference(gaps["friend"], gaps["computer"]),
                ratings_qc_pass=str(not reasons).lower(), ratings_qc_reason=";".join(reasons) or NA)


def expected(args):
    bids, output = args.bids_root, args.output_dir
    roster, omitted = study_roster(bids, args)
    commit, candidates, contents = sources(args.source_repo, args.source_ref, omitted)
    eligible_sources = set(candidates) & roster
    if not eligible_sources:
        raise ValueError("No ratings files match the BIDS roster")
    products = {bids / (SUFFIX + ".json"): (ROOT / "code" / (SUFFIX + ".json")).read_bytes()}
    audit, summary = [], []
    for pid in sorted(roster | candidates.keys()):
        files = candidates.get(pid, [])
        chosen = select_file(pid, files) if files and pid in roster else None
        selected = []
        for filename in sorted(files):
            raw = contents[filename]
            try:
                blocks = read_attempts(raw)
            except (ValueError, KeyError, UnicodeError) as error:
                raise ValueError(f"Malformed ratings in {filename}: {error}") from error
            index = selected_block(blocks) if filename == chosen else None
            for i, block in enumerate(blocks or [[]]):
                selection = "unlinked_to_roster" if pid not in roster else "superseded"
                relative = NA
                if index == i:
                    selection, selected = "selected", block
                    relative = f"{pid}/ses-01/beh/{pid}_ses-01_{SUFFIX}.tsv"
                    products[bids / relative] = tsv(ITEMS, block)
                elif filename == chosen and index is None:
                    selection = "empty_source"
                audit.append(dict(source_participant_id=pid, source_file=filename,
                                  source_sha256=digest(raw), block=i+1 if blocks else NA,
                                  n_items=len(block), n_responses=sum(r["response"] != NA for r in block),
                                  selection=selection, bids_file=relative))
        if pid in roster:
            summary.append(model_row(pid, selected, bool(chosen)))
    products[output / "ratings_summary.tsv"] = tsv(summary[0], summary)
    products[output / "sources.tsv"] = tsv(SOURCE_FIELDS, audit)
    counts = dict(roster=len(roster), statuses=dict(Counter(row["ratings_status"] for row in summary)),
                  responses=sum(row["n_responses"] for row in summary),
                  ratings_qc_pass=sum(row["ratings_qc_pass"] == "true" for row in summary),
                  unlinked_source_ids=len(candidates.keys() - roster),
                  superseded_blocks=sum(r["selection"] == "superseded" for r in audit))
    provenance = dict(source_repository="DVS-Lab/rf1-sra", source_commit=commit,
                      exporter_sha256=digest(Path(__file__).read_bytes()),
                      bids_dictionary_sha256=digest(products[bids / (SUFFIX + ".json")]),
                      participants_sha256=digest((bids / "participants.tsv").read_bytes()),
                      source_exclusion_ids_sha256=digest("\n".join(sorted(omitted)).encode()),
                      summary_sha256=digest(products[output / "ratings_summary.tsv"]),
                      source_manifest_sha256=digest(products[output / "sources.tsv"]), counts=counts)
    products[output / "provenance.json"] = as_json(provenance)
    return products, counts


def run(args):
    products, counts = expected(args)
    extra = set(args.bids_root.glob(f"sub-*/ses-01/beh/*_ses-01_{SUFFIX}.tsv")) - products.keys()
    if extra:
        raise ValueError(f"{len(extra)} unplanned Wave 1 post-ratings TSVs in BIDS. Reconcile before exporting.")
    missing = []
    for path, data in products.items():
        if path.is_symlink() or (path.exists() and path.read_bytes() != data):
            raise ValueError(f"Existing output differs from source or is a symlink. Preserve and review: {path}")
        if not path.exists():
            missing.append(path)
    if args.check and missing:
        raise ValueError(f"{len(missing)} expected files missing. First: {missing[0]}")
    if args.apply:
        for path in missing:
            path.parent.mkdir(exist_ok=True, parents=True)
            atomic_write(path, products[path])
    if args.apply or args.check:
        if any(path.read_bytes() != data for path, data in products.items()):
            raise ValueError("Installed ratings failed source comparison")
    print(json.dumps(counts, sort_keys=True))
    print(f"CHECK PASSED: {len(products)} files verified." if args.apply or args.check else
          f"Preview: {len(missing)} of {len(products)} expected files would be created.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT,
                        help="Canonical RF1 Linux2 project containing bids/ and derivatives/.")
    parser.add_argument("--source-repo", type=Path, help="Defaults to the sibling rf1-sra clone.")
    parser.add_argument("--source-ref", default=WAVE1, help="Reviewed Wave 1 raw Git revision.")
    parser.add_argument("--bids-root", type=Path, help="Defaults to PROJECT_ROOT/bids.")
    parser.add_argument("--output-dir", type=Path,
                        help="Defaults to PROJECT_ROOT/derivatives/behavioral/sharedreward/ses-01.")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--exclusions-root", type=Path, default=Path(os.environ.get(
        "SOURCEDATA_EXCLUSIONS_ROOT", "/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions")))
    scope.add_argument("--local-snapshot", action="store_true",
                       help="Use the fingerprint-verified offline copy of the Linux2 roster and exclusions.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Install missing files after full preflight.")
    mode.add_argument("--check", action="store_true", help="Require byte-for-byte agreement with Git inputs.")
    try:
        args = parser.parse_args()
        project = args.project_root.resolve()
        args.source_repo = args.source_repo or project.parent / "rf1-sra"
        args.bids_root = args.bids_root or project / "bids"
        args.output_dir = args.output_dir or project / "derivatives/behavioral/sharedreward/ses-01"
        if args.apply:
            # Share the existing BIDS participant-writer lock while installing against its roster.
            with locked(args.bids_root):
                run(args)
        else:
            run(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f"ERROR: {error}")


if __name__ == "__main__":
    main()
