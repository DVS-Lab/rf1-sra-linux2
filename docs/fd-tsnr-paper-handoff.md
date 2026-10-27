# Corrected FD, tSNR and Coverage Handoff

October 27, 2026: the original coverage95 handoff enforced coverage and settled
decisions but treated FD and tSNR flags as descriptive. That did not implement
the intended paper policy. This replacement adds the intended exclusions without
changing old handoffs, QC tables, processing outputs or settled decisions.

## Policy

- Mean FD above Q3 + 1.5 IQR excludes that run.
- tSNR below Q1 - 1.5 IQR excludes that run.
- Coverage below 95% excludes that run. Exactly 95% passes.
- Use the existing canonical QC reference mask, not a new anatomical target.
- Missing/invalid required metrics withhold the run for review, never pass it.
- Compute fences once within each task/session over the full canonical QC
  population, not the age-55+ or paper subset. Verify the recorded canonical
  thresholds and flags against those calculations before selection.
- Apply all three criteria together. Do not refit fences after removing runs.
- No TEDANA-count, aggregate-outlier, scanner-era, or smoothness exclusion.
- Preserve every previously withheld run and all current recorded holds/source
  exclusions. No subject is restored by this correction.
- These papers remain age-55+, ses-01 activation, no-TEDANA nuisance regressors.
  Ses-02 and other tasks cannot exclude a run. Select UGR paired L2 only when
  both runs pass; otherwise select the existing passing-run L1. Social Doors
  and Doors are separate inputs, not a combined L2.

## Linux2 Commands

Run after checkout-dependent processing has stopped. The sync helper refuses
tracked edits/divergence and backs up identical published logs before a fast
forward. It does not delete processing outputs or lock files.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git fetch origin
python3 code/sync_published_checkout.py --project "$PWD" --apply --processing-stopped
bash code/run_fd_tsnr_handoff.sh
)
```

The launcher builds into a new timestamped `work/coverage95-fd-tsnr-handoff-*`
directory, independently checks the result, prints the validated counts and exact
replacement paths, and publishes the run record with:

```bash
python3 code/publish_run_logs.py --project "$PWD"
```

It uses the existing `tedana-26.0.3` Python environment only as a runtime; it does
not run TEDANA, MRIQC, fMRIPrep or FEAT. The original coverage95 directory remains
unchanged. The launcher preserves `umask 0000` and restricts numerical libraries
to one thread during validation. Validation may take several minutes.

## Evidence and Outputs

`handoff_fd_tsnr.py` checks the old handoff's output hashes, its recorded processing
plan hash, and the selected completion receipts and FEAT products. It does not
rerun the old launcher's live-source/code checks: those describe historical
processing and can legitimately differ following the installed repairs and QC
refresh. This is reuse of verified completed outputs, not permission to rerun a
stale processing plan. Newly selected single-run L1 outputs are validated too.
Changes during validation stop publication; a missing selected output is an
error, not an additional scientific exclusion.

- `counts.tsv`: unique imaging Ns; paper Ns only when paper rosters were supplied.
- `selection_changes.tsv`: each prior selected participant's old/new run subset,
  L1/L2 level, and reasons. Shows removals and paired-to-single-run changes.
- `run_decisions.tsv`: original decision, all current metric decisions and fences,
  combined failure reasons, and preserved settled holds.
- `thresholds_used.tsv`: reproducible canonical task/session FD/tSNR fences.
- `{socialdoors,ugr,doors}/selected_inputs.tsv`: one input per subject/contrast.
- `{socialdoors,ugr,doors}/subjects.txt`: unique selected imaging participants.
- `provenance.json`: frozen source signatures, policy and output hashes.

The old 137/145 imaging counts and 110/116 environmental-cohort counts are not
final Ns under this corrected policy. Jacob must intersect the replacement input
tables with the same approved October 26 survey/linkage workbooks. Do not restart
survey screening or reinstate an excluded participant. Use replacement UGR paths,
not a subject-only filter on the old paired L2 table.

Exact paper counts can also be generated here by supplying `--katie-cohort` and
`--sophia-cohort` to the launcher. Each file must be an approved CSV/TSV with one
unambiguous `subject`, `participant_id`, or `rf1_id` column and unique IDs. The
files' paths are not currently available in this repository, so the default
command deliberately reports imaging Ns, not invented final paper Ns. Supplied
rosters produce `papers/*/selected_inputs.tsv` and `paper_membership.tsv` with
participant-level nonselection reasons.

Do not share a replacement handoff until its check exits zero. After that,
regenerate L3 inputs using its exact paths and the unchanged paper covariates.
No scientific approval or re-review of settled exclusions is needed.
