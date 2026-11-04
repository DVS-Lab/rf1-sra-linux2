#!/usr/bin/env python3
"""Read-only survey availability and paired-QC inventory, never a cohort selector."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys


SCORES = {
    "loneliness": "uclal_score",
    "need_to_belong": "nbs_adult_sum",
    "depressive_symptoms": "susd_adult_depression",
    "age": "sub_age",
}
MISSING = {"", "na", "n/a", "nan", "none", "null"}
ID_COLUMNS = ("rf1_id", "sub_id_rf1_data", "participant_id", "subject")
RELEVANT = re.compile(r"lonel|ucla|belong|nbs_|susd_|depress|seven.?up|seven.?down", re.I)
PRUNE = {".git", "bids", "derivatives", "stimuli", "work", "logs", "node_modules",
         "__pycache__", ".venv", "venv", "venv-report", ".venv-linux2"}
LIMITATIONS = [
    "Inventory only: no cohort, eligibility, exclusions, designs or images are changed.",
    "Finite exported scores are not item-verified scores; instrument version, range, "
    "sentinel codes, reverse keys and missing-item rules require the data dictionary.",
    "Blank totals do not distinguish not collected from incomplete or unlinked records.",
    "Duplicate IDs and suffixed aliases are not silently selected or linked.",
    "Survey visits are not aligned to imaging here; separate events are never pooled.",
    "QC-only pair counts are not source-valid or analysis-ready sample sizes.",
    "No age-55, environmental-linkage, FEVS or Ecog complete-case gate is applied.",
    "No new brain association models or correlations are run.",
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def table(path):
    data = path.read_bytes()
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")),
                            delimiter="\t" if path.suffix.lower() == ".tsv" else ",")
    fields = reader.fieldnames
    if not fields or len(fields) != len(set(fields)):
        raise ValueError("missing or duplicate table columns")
    rows = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError("malformed table row")
    return fields, rows, {"path": str(path.resolve()), "sha256": sha(data), "bytes": len(data)}


def subject(value):
    value = str(value).strip().removeprefix("sub-")
    return value if re.fullmatch(r"\d{5}", value) else None


def number(value):
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


def age_band(value):
    if value is None:
        return "missing_or_nonnumeric"
    if not 18 <= value <= 120:
        return "outside_adult_inventory_range"
    return "18-34" if value < 35 else "35-54" if value < 55 else "55-64" if value < 65 else "65+"


def summarize_rows(rows, fields, id_column):
    groups = defaultdict(list)
    invalid = 0
    aliases = 0
    for row in rows:
        raw = row[id_column].strip()
        sub = subject(raw)
        if sub is None:
            invalid += 1
            aliases += bool(re.fullmatch(r"(?:sub-)?\d{5}_duplicate", raw, re.I))
        else:
            groups[sub].append(row)
    unique = [r[0] for r in groups.values() if len(r) == 1]
    measures = {}
    for name, column in SCORES.items():
        if column not in fields:
            measures[name] = {"column": column, "status": "column_absent"}
            continue
        finite = [number(r[column]) for r in unique]
        values = [v for v in finite if v is not None]
        measures[name] = {
            "column": column, "status": "exported_not_scoring_verified",
            "n_finite_unique_id_records": len(values),
            "n_blank_or_missing_token": sum(r[column].strip().lower() in MISSING for r in unique),
            "n_other_nonnumeric_or_nonfinite": sum(v is None and r[column].strip().lower() not in MISSING
                                                     for r, v in zip(unique, finite)),
            "minimum_as_exported": min(values) if values else None,
            "maximum_as_exported": max(values) if values else None,
        }
    complete = [r for r in unique if all(c in fields and number(r[c]) is not None for c in SCORES.values())]
    bands = {}
    for band in ("18-34", "35-54", "55-64", "65+", "missing_or_nonnumeric", "outside_adult_inventory_range"):
        records = [r for r in unique if age_band(number(r.get(SCORES["age"]))) == band]
        bands[band] = {"n_unique_records": len(records), **{
            name: sum(c in fields and number(r[c]) is not None for r in records)
            for name, c in SCORES.items() if name != "age"}}
    return {
        "n_rows": len(rows), "n_valid_rf1_ids": len(groups),
        "n_invalid_or_missing_id_rows": invalid, "n_unresolved_duplicate_suffix_rows": aliases,
        "n_repeated_rf1_ids": sum(len(v) > 1 for v in groups.values()),
        "n_unique_id_records": len(unique), "measures": measures,
        "n_all_four_finite_unique_id_records": len(complete),
        "n_all_four_finite_adult_records": sum(18 <= number(r[SCORES["age"]]) <= 120 for r in complete),
        "age_strata_descriptive_only": bands,
    }


def survey_inventory(path):
    fields, rows, signature = table(path)
    ids = [c for c in ID_COLUMNS if c in fields]
    result = {"source": signature, "n_rows": len(rows),
              "relevant_columns": [c for c in fields if RELEVANT.search(c)],
              "candidate_identity_columns": ids,
              "age_or_visit_columns": [c for c in fields if re.search(r"age|date|visit|event|repeat", c, re.I)]}
    if len(ids) != 1:
        result["status"] = "review_identity_columns"
        return result, signature
    result.update(status="inventory_not_scoring_or_visit_validated", id_column=ids[0],
                  whole_file=summarize_rows(rows, fields, ids[0]))
    if "redcap_event_name" in fields:
        events = sorted({r["redcap_event_name"] for r in rows})
        result["by_redcap_event"] = {event: summarize_rows(
            [r for r in rows if r["redcap_event_name"] == event], fields, ids[0]) for event in events}
    return result, signature


def discover(roots):
    """Bounded header search; never traverse images, processing releases or symlinks."""
    found, skipped = [], Counter()
    seen = set()
    for root in roots:
        root = root.resolve()
        if not root.is_dir():
            skipped["unavailable_root"] += 1
            continue
        def onerror(error):
            raise error
        for current, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
            base = Path(current)
            depth = len(base.relative_to(root).parts)
            dirs[:] = sorted(d for d in dirs if d not in PRUNE and not d.startswith("venv-")
                             and not (base / d).is_symlink()) if depth < 4 else []
            for name in sorted(files):
                path = base / name
                if path.suffix.lower() not in {".csv", ".tsv"} or path.is_symlink():
                    continue
                resolved = str(path.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                with path.open("rb") as handle:
                    header = handle.readline(65537)
                if len(header) > 65536:
                    skipped["header_over_64KiB"] += 1
                    continue
                try:
                    fields = next(csv.reader([header.decode("utf-8-sig")],
                                             delimiter="\t" if path.suffix.lower() == ".tsv" else ","))
                except (UnicodeError, csv.Error, StopIteration):
                    skipped["unreadable_header"] += 1
                    continue
                relevant = [f for f in fields if RELEVANT.search(f)]
                if relevant:
                    found.append({"path": resolved, "relevant_columns": relevant,
                                  "identity_columns": [c for c in ID_COLUMNS if c in fields]})
    return {"candidates": found, "skipped": dict(skipped),
            "scope": "CSV/TSV headers only, max depth 4, no work/bids/derivatives/stimuli/symlinks; "
                     "not an exhaustive search of all private exports or XLSX workbooks"}


def qc_inventory(project):
    fields, rows, signature = table(project / "qc/run_qc.tsv")
    required = {"subject", "session", "task", "run", "brain_coverage_pct", "fd_mean_outlier", "tsnr_outlier"}
    if not required <= set(fields):
        raise ValueError("canonical run-QC columns unavailable")
    pairs = defaultdict(dict)
    for row in rows:
        if row["task"] not in {"socialdoors", "doors"}:
            continue
        sub = subject(row["subject"])
        if sub is None or not re.fullmatch(r"\d{2}", row["session"]) or row["run"] != "1":
            raise ValueError("unexpected paired task QC key")
        pair = pairs[(sub, row["session"])]
        if row["task"] in pair:
            raise ValueError("duplicate paired task QC key")
        pair[row["task"]] = row
    sessions = {}
    for session in sorted({ses for _, ses in pairs}):
        groups = [p for (_, ses), p in pairs.items() if ses == session]
        both = [p for p in groups if set(p) == {"socialdoors", "doors"}]
        passing = 0
        unresolved = 0
        for pair in both:
            measured = all(number(r["brain_coverage_pct"]) is not None
                           and 0 <= number(r["brain_coverage_pct"]) <= 100
                           and r["fd_mean_outlier"].lower() in {"true", "false"}
                           and r["tsnr_outlier"].lower() in {"true", "false"} for r in pair.values())
            unresolved += not measured
            passing += measured and all(number(r["brain_coverage_pct"]) >= 95
                                        and r["fd_mean_outlier"].lower() == "false"
                                        and r["tsnr_outlier"].lower() == "false" for r in pair.values())
        sessions[session] = {"n_with_either_task_qc_record": len(groups),
                             "n_with_both_task_qc_records": len(both),
                             "n_both_recorded_fd_tsnr_clear_coverage95": passing,
                             "n_pairs_with_missing_or_invalid_qc": unresolved}
    return {"source": signature, "by_session": sessions,
            "scope": "QC-record inventory, not source-validity or eligibility approval. "
                     "Recorded FD/tSNR flags and >=95% coverage are summarized, not recomputed. "
                     "No cross-task/session propagation or TEDANA-count gate."}, signature


def build(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
              "final_cohort_assigned": False, "limitations": LIMITATIONS,
              "surveys": [], "sources": [], "tool_sha256": sha(Path(__file__).read_bytes())}
    paths = {p.resolve() for p in args.survey}
    report["discovery"] = discover(args.discover_root)
    paths.update(Path(c["path"]) for c in report["discovery"]["candidates"]
                 if set(SCORES.values()) & set(c["relevant_columns"]))
    for path in sorted(paths):
        profile, signature = survey_inventory(path)
        report["surveys"].append(profile)
        report["sources"].append(signature)
    if args.project:
        report["qc_records"], signature = qc_inventory(args.project.resolve())
        report["sources"].append(signature)
    for source in report["sources"]:
        if sha(Path(source["path"]).read_bytes()) != source["sha256"]:
            raise ValueError("input changed during inventory")
    (output / "inventory-private.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("INVENTORY COMPLETE: no inputs, cohort, exclusions or running jobs changed.")
    print("Candidate survey tables:", len(report["discovery"]["candidates"]))
    for candidate in report["discovery"]["candidates"]:
        print("CANDIDATE TABLE:", candidate["path"],
              "FIELDS:", json.dumps(candidate["relevant_columns"]))
    print("Discovery scope:", report["discovery"]["scope"])
    print("Unavailable roots/skipped headers:", json.dumps(report["discovery"]["skipped"], sort_keys=True))
    for profile in report["surveys"]:
        data = profile.get("whole_file")
        if data:
            print("SURVEY", Path(profile["source"]["path"]).name,
                  "unique-ID records:", data["n_unique_id_records"],
                  "all-four finite (not scoring/visit validated):", data["n_all_four_finite_unique_id_records"])
            print("MEASURE AVAILABILITY:", json.dumps({name: {
                k: v for k, v in summary.items() if k not in {"minimum_as_exported", "maximum_as_exported"}}
                for name, summary in data["measures"].items()}, sort_keys=True))
            print("IDENTITY COUNTS:", json.dumps({k: data[k] for k in (
                "n_rows", "n_valid_rf1_ids", "n_repeated_rf1_ids", "n_invalid_or_missing_id_rows",
                "n_unresolved_duplicate_suffix_rows")}, sort_keys=True))
            print("AGE-STRATIFIED AVAILABILITY:", json.dumps(data["age_strata_descriptive_only"], sort_keys=True))
        else:
            print("SURVEY ID-COLUMN REVIEW REQUIRED:", profile["source"]["path"],
                  json.dumps(profile["candidate_identity_columns"]))
    if "qc_records" in report:
        print("QC-RECORD COUNTS, NOT FINAL ELIGIBILITY:", json.dumps(report["qc_records"]["by_session"], sort_keys=True))
    print("PRIVATE REPORT:", output / "inventory-private.json")
    print("NEXT: verify current questionnaire source, instrument/scoring dictionary, visit linkage, "
          "and live source-valid paired imaging. No final N assigned.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--project", type=Path, help="Linux2 root; reads QC table only, not images")
    parser.add_argument("--survey", action="append", type=Path, default=[])
    parser.add_argument("--discover-root", action="append", type=Path, default=[])
    args = parser.parse_args()
    os.umask(0o000)
    try:
        build(args)
    except (OSError, ValueError, UnicodeError, csv.Error) as error:
        print("STOPPED:", type(error).__name__, "- no input files changed; inspect supplied paths/schema.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
