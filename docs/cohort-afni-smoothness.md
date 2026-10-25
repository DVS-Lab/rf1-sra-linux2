# Cohort QC Refresh And AFNI Smoothness

## Measurement contract

Use exactly the baseline measurement employed by `sharedreward-aging` and
`rf1-sra-sharedreward`. The former delegates to the latter's
`code/measure_smoothness.sh`, which runs:

```bash
3dFWHMx -ShowMeClassicFWHM -detrend -mask "$mask" -acf NULL -input "$bold"
```

This pass copies and hashes that authoritative wrapper into its output
directory. It measures **unsmoothed, non-echo fMRIPrep MNI152NLin6Asym BOLD**
with its matching fMRIPrep brain mask. It reports classic x/y/z/combined FWHM
and ACF a/b/c/effective FWHM. These are not MRIQC's raw-BIDS voxel-unit FWHM,
an applied smoothing kernel, or task-model residual ACF estimates. Do not pool
the MRIQC and AFNI columns as if they measured the same stage.

All tasks and sessions are inventoried from the union of active raw BIDS,
non-echo MNI fMRIPrep outputs, and canonical run QC. Echo-specific and phase
derivatives are not duplicate measurement units; archived/work directories
are not searched. There is no age-55 cutoff, ses-01 restriction, or exclusion
for a QC flag, incomplete QC row, or behavioral task-validity hold. Measurement
does not grant analysis eligibility. Existing source-excluded subjects remain
parked and explicitly counted. Missing/ambiguous BOLD, missing masks, invalid
geometry, or failed results remain visible and make the final check fail.

Descriptive summaries and boxplots are grouped by exact task and session,
then scanner era. Doors and Social Doors remain separate. Both run and subject
counts are reported; runs are not assumed independent participants. Unknown
eras remain unknown. No smoothness exclusion or target is chosen. In particular,
Shared Reward's approved 6-mm target is **not** automatically approved here.

## Linux2: Launch

Run from a normal Linux2 shell after the code has been published and no process
depends on the old checkout. The synchronization helper preserves published
records and refuses unrelated tracked edits; never use reset/clean to bypass it.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git fetch origin
git show origin/main:code/sync_published_checkout.py |
  python3 - --project "$PWD" --apply --processing-stopped

STAMP=qc-afni-smoothness-$(date +%Y%m%d-%H%M%S)
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  bash code/refresh_qc_smoothness.sh \
    --output "$PWD/work/cohort-smoothness-v1" --jobs 16 \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 < /dev/null &
echo "STAMP=$STAMP"
sleep 5
tail -30 "logs/runs/${STAMP}.nohup.out"
)
```

One AFNI measurement per job, one OpenMP thread each. `--jobs` controls
concurrency, not the estimator. The script uses the existing official AFNI
installation at
`/ZPOOL/data/tools/anaconda/tug87422/envs/sharedreward-phase0/afni-bin`, and
the TEDANA environment's Python for its existing NIfTI/QC dependencies.
`AFNI_BIN_DIR` and `AUDIT_PYTHON` may override those paths explicitly.
Preflight stops before touching QC if the dependencies/wrapper are missing.

The script backs up the entire current `qc/` directory under
`work/cohort-smoothness-v1/qc-before`, refreshes/checks canonical QC with its
existing task/session policy, and refreshes/checks descriptive scanner-era QC.
It then freezes the measurement inventory and measures the cohort. An existing
plan skips the QC rebuild and validates completed measurements before reusing
them. SHA-256 checks read full compressed inputs, so verification also takes
time and I/O even when AFNI does not need to rerun.

Completed results are atomic and immutable. Interrupted/failed attempts remain
under `attempts/`; rerunning the same launch without the Git-sync block retries
only missing results. A corrupt completed result, changed input, new scan,
changed QC, changed wrapper/code, or changed AFNI executable stops reuse for
review. Never delete completed results to force a retry. Use a new versioned
output directory for a genuinely changed input cohort.

No imaging, masks, completed TEDANA experiment, settled exclusions, task
manifests, L1/L2 outputs, or paper selections are changed by this command.
The post-install task-manifest/downstream rebuild remains a separate closeout.
The installation receipt is historical: its original unchanged-QC assertion
is not a post-refresh QC validator; do not rerun installation to satisfy it.

## Linux2: Progress And Logs

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
pgrep -u "$USER" -af '[m]easure_cohort_smoothness.py|[3]dFWHMx' || true
for log in logs/runs/qc-afni-smoothness-*.nohup.out; do
  [ -f "$log" ] || continue
  printf '\n%s\n' "$log"
  tail -15 "$log"
done
```

After completion, the full-log run record includes inventory counts,
per-run completion/failure messages, task/session/era median summaries and
the final completeness result. Publish it with the usual append-only helper:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
python3 code/publish_run_logs.py --project "$PWD"
```

The output directory contains `inventory.tsv`, `run_metrics.tsv`, `summary.tsv`,
`report.md`, `figures/`, per-run results/receipts, the frozen wrapper, and
`plan.json`. The canonical QC refresh intentionally modifies tracked QC tables
and figures. The log publisher does not commit those changes: leave them for
review, do not `git add .` or discard them. No new imaging eligibility decisions
are encoded by the refreshed statistical flags.

## Verification scope

Local regression tests use synthetic NIfTI data and a test-only shell
measurement wrapper. They exercise inventory coverage, source exclusions,
geometry validation, preservation/restarts, invalid results, failure handling,
and task/session separation, plus rendering. They do not substitute for a
real Linux2 AFNI run or establish a smoothness result for this cohort.
