"""Print aggregate PCA-method comparisons from the frozen TEDANA audit (no imaging I/O)."""

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median


METHODS = {"nss-fastica": "AIC", "nss-kic-fastica": "KIC", "nss-mdl-fastica": "MDL"}
IDENTITY = ("subject", "session", "task", "run", "software_versions")


def read_paired(root):
    validation = json.loads((root / "validation.json").read_text())
    raw = (root / "manifest.json").read_bytes()
    if (validation.get("validated") is not True or validation["failures"] != 0 or
            hashlib.sha256(raw).hexdigest() != validation["manifest_sha256"]):
        raise ValueError("need a passed validation for this exact frozen manifest")
    roster = json.loads(raw)["rows"]
    frozen = {r["run_key"]: tuple(str(r[k]) for k in IDENTITY) for r in roster}
    n = len(frozen)
    if not n or len(roster) != n or n != validation["expected_runs"] or not (
        validation["expected_jobs"] == validation["summary_rows"] == 3 * n
    ):
        raise ValueError("inconsistent validated cohort size")
    pairs = defaultdict(dict)
    with (root / "component_summary.tsv").open(newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            key, method = row["run_key"], METHODS[row["config"]]
            if frozen.get(key) != tuple(row[k] for k in IDENTITY) or method in pairs[key]:
                raise ValueError("duplicate method or run metadata differs from manifest")
            total, rejected = int(row["total_components"]), int(row["rejected_components"])
            if not 0 <= rejected <= total or total == 0 or not math.isclose(
                rejected / total, float(row["rejected_fraction"]), abs_tol=1e-8
            ):
                raise ValueError("invalid component counts or fraction")
            pairs[key][method] = (total, rejected)
    if set(pairs) != set(frozen) or any(len(p) != 3 for p in pairs.values()):
        raise ValueError("incomplete three-method pairing")
    return [(frozen[k], p) for k, p in pairs.items()]


def report(pairs, out):
    groups = defaultdict(list)
    for (subject, session, task, run, version), p in pairs:
        groups[session, task, version].append((subject, p))
    fields = ["session", "task", "scanner_software", "runs", "subjects"]
    for method in METHODS.values():
        fields += [method + col for col in ("_total", "_rejected", "_rejected_pct")]
    w = csv.writer(out, delimiter="\t", lineterminator="\n")
    w.writerow(fields + ["median_within_run_MDL_minus_AIC_rejected"])
    for key, samples in sorted(groups.items()):
        row = [*key, len(samples), len({s for s, _ in samples})]
        for method in METHODS.values():
            counts = [p[method] for _, p in samples]
            row += [median(t for t, r in counts), median(r for t, r in counts),
                    round(median(100 * r / t for t, r in counts), 1)]
        w.writerow([*row, median(p["MDL"][1] - p["AIC"][1] for _, p in samples)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path,
                        default=Path("derivatives/tedana-audit/cohort-pca-v1"))
    pairs = read_paired(parser.parse_args().audit_root)
    print(f"Verified {len(pairs)} complete matched runs. Medians are per run; not exclusions.")
    report(pairs, sys.stdout)
