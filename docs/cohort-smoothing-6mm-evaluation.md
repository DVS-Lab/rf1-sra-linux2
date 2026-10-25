# Isolated 6-mm Smoothing Evaluation

This is an evaluation, not a production migration. It preserves existing BOLD,
confounds, completed TEDANA, QC thresholds, source-validity decisions, manifests,
and paper selections. No FEAT or task-level analyses are launched.

## Method And Scope

- All ready runs in the completed `work/cohort-smoothness-v1` inventory, across
  all tasks, sessions, and ages. QC flags do not filter the evaluation. Explicit
  source exclusions remain parked and are counted separately.
- Input: unsmoothed, non-echo fMRIPrep `MNI152NLin6Asym` BOLD with its matching
  brain mask. This is not MRIQC's raw-BIDS smoothness measurement.
- Freeze the actual `smooth_to_target.sh`, `measure_smoothness.sh`, and
  `project_config.sh` from Linux2's `rf1-sra-sharedreward/code`.
- Use `3dBlurToFWHM` to reach **6 mm total classic combined FWHM**, not add a
  6-mm kernel. Preserve Shared Reward's default blurmaster behavior. No automatic
  `-bmall` retry or adoption of its run-specific exceptions.
- Remeasure with the same `3dFWHMx -ShowMeClassicFWHM -detrend -mask ... -acf NULL`
  method, executable identity, and mask as the completed baseline.
- Report classic directional and combined FWHM plus ACF parameters/effective
  FWHM. **5.4-6.6 mm is the evaluation band for classic combined FWHM only**.
  Matching that scalar does not ensure identical anisotropy or ACF across eras.
- Inputs already at/above 6 mm remain untouched and require target review.
  They get no invented after value and are not newly excluded. Axis values
  at/above 6 mm are also counted, even if combined FWHM is below target.
- Valid outputs outside the evaluation band remain in paired plots and tables.
  They are not automatically rerun, silently dropped, or marked eligible.

Reference: [AFNI 3dBlurToFWHM](https://afni.nimh.nih.gov/pub/dist/doc/program_help/3dBlurToFWHM.html).
It cannot undo existing smoothness. A future production adoption would require
an explicit decision, FEAT smoothing disabled, and separate downstream rebuilds.

## 1. Linux2: Synchronize And Inspect The Upper Tail

Start only after the baseline measurement has completed. These commands assume
the checkout is clean; if `git pull --ff-only` fails, stop and inspect rather
than resetting or forcing. Do not change tracked measurement code or QC tables
while the evaluation runs: their identities are frozen and checked.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
git status --short
git pull --ff-only
STAMP=smoothness-6mm-plan-$(date +%Y%m%d-%H%M%S)
bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  bash code/run_smoothness_6mm.sh plan
cat derivatives/smoothness-evaluation-6mm-v1/upper_tail.md
```

Plan is read-only with respect to imaging data. It validates baseline receipts,
result hashes, input stamps, and measurement-method identity. Full input hashes
are rechecked before processing and final validation. Do not repeat `plan` once
it exists; use `run` or `check`. The upper-tail values are determined on Linux2,
not inferred from the earlier median summaries.

## 2. Linux2: Launch Or Resume

Start at 16 single-threaded workers. Smoothing has a different memory profile
from measurement; CPU count alone does not justify 48 concurrent workers.
The script checks a conservative float-output disk estimate before launching.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
mkdir -p logs/runs
STAMP=smoothness-6mm-evaluation-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  bash code/run_smoothness_6mm.sh run --jobs 16 --threads 1 \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "STAMP=$STAMP"
sleep 5
tail -30 "logs/runs/${STAMP}.nohup.out"
```

The same launch block resumes an interrupted evaluation. Do not overwrite or
delete completed results. Every existing result must pass lineage, image hash,
measurement hash, geometry, volume-count, TR, and finite-value checks before it
is reused. Failed attempts stay in `attempts/`; completed results stay in
`runs/`. Locks inherited by subprocesses prevent an overlapping restart while
old workers are still alive. If locked, wait; do not delete lock files.

The launcher runs the full check after processing, even if some workers fail.
`check` writes plots, tables, and `validation.json`:

- `CHECK PASSED`: all active runs have verified outputs in the classic band.
- `EVALUATION COMPLETE; TARGET REVIEW REQUIRED`: processing is technically
  complete, but some baseline runs were held or achieved values outside the
  band. Exit 1 deliberately requests review, **not exclusions or automatic reruns**.
- `CHECK FAILED`: missing/invalid processing results need attention. Inspect
  `run_results.tsv` and the referenced attempt logs.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
pgrep -u "$USER" -af '[e]valuate_smoothness_6mm.py|[3]dBlurToFWHM|[3]dFWHMx' || true
tail -40 "$(ls -t logs/runs/smoothness-6mm-evaluation-*.nohup.out | head -1)"
free -h
```

After the runner exits, inspect the **newest log's final check**. A pre-existing
validation file from an earlier attempt is not proof that a running attempt
finished. A check can be rerun independently with logging:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
STAMP=smoothness-6mm-check-$(date +%Y%m%d-%H%M%S)
bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  bash code/run_smoothness_6mm.sh check
cat derivatives/smoothness-evaluation-6mm-v1/validation.json
```

## 3. Share Reports And Plots Through Git

After processing/check have stopped, export reports even when target review is
required: those results must remain visible. Only new evaluation reports and
figures are copied into `qc/smoothness_evaluation_6mm/`. Canonical QC tables and
existing scanner-era figures are not modified. Images, per-run receipts, and
the complete run-level table remain under the ignored evaluation directory.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
bash code/run_smoothness_6mm.sh export
git add -- qc/smoothness_evaluation_6mm/ logs/records/
git diff --cached --stat
git commit -m "Record isolated 6 mm smoothness evaluation"
git push
```

No SCP or special publisher is needed for these reports. If the push is rejected,
do not force; preserve the local commit and reconcile the newer remote commits.

## Outputs

`derivatives/smoothness-evaluation-6mm-v1/` contains:

- `upper_tail.tsv` / `upper_tail.md`: full-baseline task/session/era quantiles,
  maxima, threshold counts, and identifiers of held runs.
- `baseline_runs.tsv`: all measured baseline runs and directional upper-tail flags.
- `run_results.tsv`: paired metrics, held/failed cases, original QC flags, paths.
- `paired_summary.tsv`: same-run before/after medians and quartiles, plus counts
  of runs, participants, held runs, failures, and out-of-band results.
- `figures/*_baseline.png`: all-baseline empirical distributions by scanner era.
- `figures/*_before_after.png`: paired boxplots and per-run scatterplots for
  classic and ACF effective FWHM, independently for every task/session present.
- `validation.json`, `plan.json`, per-run receipts: checks and reproducible lineage.

Run counts are not independent participant counts. Small scanner-era/session
cells remain visible but should not be overinterpreted. No hypothesis test or
automatic scanner-era correction is used here.
