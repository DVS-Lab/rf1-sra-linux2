# Social Doors Minus Doors: Diagnostic, Not Final Exclusions

October 27, 2026: the diagnostic and review are complete. See the
[results and 121-pair strict input table](../qc/paired_difference/socialdoors-v1/README.md).
The recommendation is to retain the already-specified FD/tSNR policy for the
primary analysis and use the broader 135-pair set only as a labeled sensitivity
analysis. The diagnostic itself assigned no final exclusions. Sophia's verified
UGR selection is unchanged.

## Scope and Safeguards

- Use the verified age-55+, ses-01, base-confounds/no-TEDANA L1 plan.
- Require both Social Doors and Doors, each with canonical coverage >=95%.
- Preserve original and current source exclusions, reviewed holds, unavailable
  inputs, and missing/invalid QC measurements. Restore only runs withheld solely
  for known high-FD/low-tSNR flags. Label those flags; do not erase the decisions.
- Read completed COPE, VARCOPE, mask, design, receipt and DOF files. Do not run
  FEAT, preprocessing, MRIQC, TEDANA, or smoothing. Existing handoffs are untouched.
- Match all four canonical contrasts: win, loss, decision, win-loss. Contrast 4
  is `(Social win - loss) - (Doors win - loss)`, not an all-trials difference.
- Subtract Social Doors minus Doors; do not use the historical cross-task L2
  **mean**. Verify matching grids without resampling.
- Compute variance as `VARCOPE_social + VARCOPE_doors` and SE as its square root.
  This assumes independent within-run estimation errors. Cross-run covariance
  is not estimated. These are descriptive maps, not new z-statistics/p-values.
- Require finite positive variance inside both masks; unsupported values are NaN,
  not zero. Retain each pair's full joint support. Cohort summaries use a fixed
  intersection across every pair/contrast, report its size, and must not be
  mistaken for the original coverage target. No new intersection cutoff is used.
- Never exclude on a large difference, large SE, or small/large difference in
  FD/tSNR. Boxplots are descriptive. Good-looking differences do not establish
  that motion canceled; extreme biological effects are not acquisition failures.

This evaluates imaging pairs, not final survey-linked paper Ns. No outcome-based
exclusions, phenotype associations, significance tests, or automatic policy
changes are made. Review full-support maps as well as common-support summaries:
the common intersection can omit peripheral artifacts.

## Linux2: Exact Commands

Run when no other job is using this checkout's code. The sync helper preserves
published logs and refuses unrelated uncommitted changes.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git fetch origin
python3 code/sync_published_checkout.py --project "$PWD" --apply --processing-stopped
bash code/run_socialdoors_difference_diagnostic.sh
)
```

The wrapper uses the verified
`work/coverage95-fd-tsnr-handoff-20261027-141630` as its source and writes only
`work/socialdoors-paired-diagnostic-v1`. It uses eight workers for small 3D
arithmetic, not whole-run processing. Re-running the same command verifies and
reuses completed pair maps; corrupted completed maps or changed inputs fail
closed. A single-output lock prevents concurrent writers. Partial maps without
a completed receipt may be regenerated only inside this new diagnostic directory.

The wrapper logs build/check and automatically runs:

```bash
python3 code/publish_run_logs.py --project /ZPOOL/data/projects/rf1-sra-linux2
```

Success requires `CHECK PASSED` and exit 0, not merely the presence of plots.
The log reports total, strict-pass and FD/tSNR-flagged paired imaging Ns.

## Review Outputs

Under `/ZPOOL/data/projects/rf1-sra-linux2/work/socialdoors-paired-diagnostic-v1/`:

- `README.md`: scope, counts and interpretation limits.
- `paired_difference_summary.png`: signed mean, RMS difference and median SE,
  separated by strict-pass versus flagged membership for all four contrasts.
- `paired_qc_associations.png`: contrast-4 difference/SE against maximum run FD,
  minimum run tSNR and their between-task differences.
- `pair_metrics.tsv`: per-subject/contrast summaries and original QC measurements.
- `diagnostic_pairs.tsv`: exact paired input paths; **not a final L3 input list**.
- `run_membership.tsv`: preserved decisions and diagnostic availability; an
  included run without an included partner does not enter paired calculations.
- `pair_membership.tsv`: unique-participant pairing status and unavailable-partner reasons.
- `pairs/sub-*/cope-*/`: full-joint-support difference, variance, SE and valid mask.
- `common_support.nii.gz`, `union_support.nii.gz`: explicit summary domains.
- `plan.json`, `artifacts.json`: frozen input hashes and verified output hashes.

## Git-Only Report Sharing

The reviewed PNGs and TSVs are now committed under
`qc/paired_difference/socialdoors-v1/`. Use Git to synchronize these reports,
tables, plots and their review documentation. Do not use scp/rsync for these
shareable artifacts. No further transfer is needed for this completed review.

For a future report update, first pass the diagnostic check, copy only its
explicit report files into this tracked report directory, inspect the diff,
and commit/push that directory. Do not add the whole ignored work directory or
NIfTI products. `publish_run_logs.py` still publishes run records only; it does
not publish plots/tables. Keep the Git-shared strict subset consistent with any
updated report and rerun its snapshot tests before publishing a changed subset.

Jacob should use the current canonical handoff README and the Git-shared matched
input table. Preserve the settled exclusions and distinguish imaging Ns from
paper Ns; there is no need to rerun this completed diagnostic for a transfer.
