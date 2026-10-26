#!/usr/bin/env python3
"""Read-only comparison of the portable QA snapshot and canonical RF1 QC."""

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path


def table(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def digest(path, compressed=False):
    before = path.stat()
    result = hashlib.sha256()
    size = 0
    with (gzip.open(path, "rb") if compressed else path.open("rb")) as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
            size += len(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"File changed during read: {path}")
    return {"uncompressed_bytes": size, "sha256": result.hexdigest()}


def compare_pair(plain, compressed):
    left, right = digest(plain), digest(compressed, compressed=True)
    return {
        "plain": str(plain), "compressed": str(compressed),
        "plain_content": left, "compressed_content": right,
        "status": "identical_uncompressed_bytes" if left == right else "different_contents",
    }


def verify_report(report):
    provenance = json.loads((report / "provenance.json").read_text())
    for name, expected in provenance["outputs"].items():
        path = (report / name).resolve()
        if report.resolve() not in path.parents:
            raise ValueError(f"Unsafe report path: {name}")
        if digest(path)["sha256"] != expected:
            raise ValueError(f"Report artifact changed: {name}")


def compare_metrics(canonical, portable, scanner):
    index = {row["image_id"]: row for row in portable}
    if len(index) != len(portable):
        raise ValueError("Duplicate image IDs in portable table")
    differences = []
    for rows, path_column, metrics in (
        (canonical, "bids_bold", (("tsnr", "tsnr"), ("fd_mean", "fd_mean"))),
        (scanner, "bids_sidecar", (("fwhm_avg_mm", "fwhm_mean_mm"),)),
    ):
        for row in rows:
            key = row[path_column].removeprefix("bids/")
            if path_column == "bids_sidecar":
                key = key.removesuffix(".json") + ".nii.gz"
            target = index.get(key)
            for original, other in metrics:
                # Report nonnumeric/missing values explicitly, never as agreement.
                try:
                    equal = target is not None and float(row[original]) == float(target[other])
                except (ValueError, TypeError):
                    equal = False
                if not equal:
                    differences.append({"image_id": key, "metric": original})
    return differences


def reconcile(project, check_anatomy=False):
    report = project / "qc/tubric_qa"
    verify_report(report)
    portable = table(report / "run_qc.tsv")
    canonical = table(project / "qc/run_qc.tsv")
    scanner = table(project / "qc/scanner_era/run_metrics.tsv")
    differences = compare_metrics(canonical, portable, scanner)
    flags = {(r["image_id"], r["metric"]): r["flag"].lower()
             for r in table(report / "flags.tsv")}
    flag_differences = [
        {"image_id": row["bids_bold"], "metric": metric}
        for row in canonical for metric in ("tsnr", "fd_mean")
        if row[metric + "_outlier"].lower() != flags.get(
            (row["bids_bold"].removeprefix("bids/"), metric))
    ]
    selected = {row["bids_bold"].removeprefix("bids/") for row in canonical}
    extra = [r for r in portable if r["suffix"] == "bold" and r["echo"] == "2"
             and r["part"] == "mag" and r["image_id"] not in selected]
    excluded = set(json.loads((project / "qc/provenance.json").read_text())
                   ["inventory"]["source_excluded_subjects"])
    issues = [{"image_id": r["image_id"], "issues": r["validation_issues"]}
              for r in portable if r["validation_issues"]]
    missing = Counter((r["suffix"], r["session"], r["mriqc_status"])
                      for r in portable if r["applicable"] == "True"
                      and r["mriqc_status"] != "available")
    result = {
        "report_artifacts_verified": True,
        "canonical_runs": len(canonical), "scanner_metric_rows": len(scanner),
        "metric_differences": differences, "flag_differences": flag_differences,
        "portable_extra_echo2_runs": len(extra),
        "extra_runs_by_subject": dict(Counter(r["subject"] for r in extra)),
        "all_extra_runs_already_source_excluded": all(r["subject"] in excluded for r in extra),
        "missing_mriqc": [dict(suffix=k[0], session=k[1], status=k[2], images=v)
                          for k, v in sorted(missing.items())],
        "identity_or_metadata_issues": issues,
        "anatomical_comparisons": [], "files_changed": False,
    }
    if check_anatomy:
        bids = (project / "bids").resolve()
        issue_ids = {row["image_id"] for row in issues}
        for row in issues:
            if row["issues"] != "duplicate_raw_identity" or not row["image_id"].endswith(".nii"):
                continue
            if row["image_id"] + ".gz" not in issue_ids:
                raise ValueError("Duplicate identity does not form a .nii/.nii.gz pair")
            plain = (bids / row["image_id"]).resolve()
            compressed = (bids / (row["image_id"] + ".gz")).resolve()
            if bids not in plain.parents or bids not in compressed.parents:
                raise ValueError("Anatomical path escapes BIDS root")
            result["anatomical_comparisons"].append(compare_pair(plain, compressed))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-anatomy", action="store_true",
                        help="Read the reported .nii/.nii.gz pairs; never modify or remove them")
    args = parser.parse_args()
    try:
        result = reconcile(args.project.resolve(), args.check_anatomy)
        print(json.dumps(result, indent=2))
        failed = (result["metric_differences"] or result["flag_differences"]
                  or not result["all_extra_runs_already_source_excluded"]
                  or any(r["status"] != "identical_uncompressed_bytes"
                         for r in result["anatomical_comparisons"]))
        print("No source files, QC rules, exclusions or imaging outputs changed.")
        return 1 if failed else 0
    except (OSError, ValueError, KeyError, EOFError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
