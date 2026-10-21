# Cohort-wide TEDANA PCA comparison

## Scope and prior coverage

The August cohort audit inspected production results and saved PCA estimates.
It was not a cohort-wide AIC/KIC/MDL rerun. The saved PCA-method report and
20260827-234407 run record validate **20 runs / 60 method-run outputs**. The
51-run sentinel experiment was another subset, not a whole-cohort variant.

`code/benchmark_tedana_cohort.py` now inventories every acquired BIDS echo-2
magnitude run in the five canonical task labels, across both sessions, excluding
subjects in the established source-exclusion directory. It does not select on
QC flags, current paper samples, or event/model eligibility. A technically
processable imaging run can be audited even when its task analysis is held;
this never releases that hold or reverses a settled exclusion.

The current canonical QC table has 2,781 runs, implying 8,343 method-run jobs if
the live Linux2 inventory is unchanged and all inputs pass preflight. The actual
inventory, not that expected number, determines coverage. Every missing or
ambiguous input is written to `blocked.tsv`; a blocked manifest cannot launch.

Methods are NSS-aware FastICA with **AIC, KIC, and MDL**. All other settings are
matched: TEDANA 26.0.3, native preprocessed echoes, explicit fMRIPrep mask,
curvefit, T2* combination, seed 42, tedana_orig tree, one computational thread.
RobustICA is not part of this PCA-only experiment. Neither is MEPrep.

## Isolation and resumption

All large outputs, inventories, per-job logs, and participant-level summaries
stay in ignored `derivatives/tedana-audit/cohort-pca-v1/`. Production BIDS,
fMRIPrep, TEDANA, confounds, canonical QC, and downstream manifests are read-only.
The script uses the existing benchmark command builder but a separate execution
and validation path suitable for an entire cohort.

- `prepare` freezes the live roster and inputs. It can be repeated only if
  unchanged. Use a new audit root for changed inputs or a new cohort.
- NIfTI input identity uses path, size, and nanosecond modification time;
  small inputs additionally use SHA256. This is an efficient change detector,
  **not cryptographic proof of image identity** against changes that preserve
  size and timestamps. Do not alter inputs or preserve their timestamps while
  this experiment is running. Image input hashes are not claimed.
- Each successful job has a completion contract, output fingerprints, elapsed
  time, and a digest of the decoded optimally combined image. Resume verifies
  the contract/fingerprints; final check decodes the images again.
- Completed jobs in this new experiment are preserved. A changed completed
  output is a failure, never automatically overwritten.
- Partial/failed directories are preserved. After inspecting the reason, an
  explicit `--retry-failed` archives each partial attempt before rerunning it.
- Old sentinel outputs are preserved in their existing directories but are
  **not imported as current results**: their provenance does not fingerprint
  current inputs, some of which were repaired since August. A fresh matched
  AIC reference also avoids mixing historical masks/settings with new criteria.
- An exclusive lock prevents concurrent commands against the same experiment;
  launched TEDANA children inherit it. It does not lock unrelated pipelines.
- Eight worker processes are used by default, one BLAS/ICA thread each. Jobs
  are scheduled independently, with start/completion messages and a heartbeat
  each minute without a completion. `progress.jsonl` is flushed after every job.
- A 100-GiB free-space reserve stops new jobs from launching below that level.
  It is not a total disk estimate. Three complete TEDANA output trees may require
  substantial disk space; inspect `df -h derivatives` before launching. Do not
  increase concurrency without checking available RAM and disk throughput.

## Linux2 commands

First update and freeze the full input inventory. This does not run ICA:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
umask 0002
export AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
df -h derivatives
bash code/run_logged.sh \
  --label "tedana-cohort-pca-prepare-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- \
  "$AUDIT_PYTHON" code/benchmark_tedana_cohort.py prepare
```

Proceed only after `blocked: 0`. The next command runs all three variants and
automatically performs the paired-product check and writes the summary:

```bash
STAMP=tedana-cohort-pca-$(date +%Y%m%d-%H%M%S)
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
    "$AUDIT_PYTHON" code/benchmark_tedana_cohort.py run --jobs 8 \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "STAMP=$STAMP"
sleep 5
tail -40 "logs/runs/${STAMP}.nohup.out"
```

Rerun that launch block to resume, without `--overwrite`. There is intentionally
no overwrite option. On a failed attempt inspect `status.tsv` and that job's
`console.log`; add `--retry-failed` only after addressing the cause.

To repeat validation without running ICA:

```bash
bash code/run_logged.sh \
  --label "tedana-cohort-pca-check-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- \
  "$AUDIT_PYTHON" code/benchmark_tedana_cohort.py check
```

Do not publish private experiment outputs. Only the compact run record belongs
in the usual log-sharing workflow. Raw TEDANA logs stay in ignored derivatives.

## What completion establishes

The checker verifies requested PCA versus selected component counts, metric
labels versus mixing columns, finite mixing/denoised/optcom data, image length,
TR, affine, and exact zero padding of NSS rows back to the original grid. It
requires identical decoded optcom images across AIC/KIC/MDL for each run.
No separate t2smap jobs or restored full-grid denoised BOLD copies are needed:
RF1 uses full-length fMRIPrep BOLD in a simultaneous task+nuisance GLM.

`component_summary.tsv` reports counts, rejected fraction, accepted/rejected
normalized component variance, base and combined
nuisance ranks including intercept, incremental TEDANA rank, and residual df
**before task regressors** using the existing production-base selection helper.
It is only valid as a complete paired summary when `validation.json` says
`validated: true` for the current manifest. Partial rows can exist after failure.

This is a first-stage experiment completion gate, not scientific approval. Next:
compare paired methods within task/session and scanner era, run actual task EV
and contrast-efficiency checks, and evaluate artifact control and signal
preservation. Do not select a method by reduced component count, increased N,
or tSNR alone. Do not regenerate canonical exclusion flags from these audit
outputs until the method and downstream policy are explicitly approved.
