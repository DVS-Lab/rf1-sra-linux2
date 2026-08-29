# TEDANA Audit And Sentinel Benchmark

This directory is the Git-tracked home for the RF1-SRA audit of historical
TEDANA 26.0.3 outputs and the small, controlled benchmark used to evaluate NSS
handling and RobustICA. It is deliberately separate from production run QC.

The historical production baseline remains under `derivatives/tedana/`. No
script in this workflow may overwrite or reinterpret those files. Large
component tables, rerun derivatives, per-run logs, and external-regressor files
remain ignored under `derivatives/tedana-audit/`.

## Scientific Questions

The workflow keeps three questions separate:

1. Does including initial non-steady-state volumes materially affect T2*/S0
   estimation or optimal combination?
2. Does excluding those volumes from PCA/ICA, or using RobustICA, improve
   unusual decompositions?
3. Which components resemble conventional rigid-body Motion24 regressors, and
   does that information add useful QC without changing TEDANA classification?

Task regressors are never used for component classification. Event timing and
the original volume-zero temporal origin remain unchanged.

## Phase 1: Read-Only Cohort Audit

`audit_tedana.py build` inventories the same acquired echo-2 magnitude BIDS
runs used by canonical `build_run_qc.py`. Subjects present in the authoritative
private source-exclusion directory are omitted from the standard inventory.

For each fMRIPrep confounds table it validates every
`non_steady_state_outlier*` regressor as binary and one-hot and requires their
rows to be exactly `0..N-1`. Missing or malformed cases remain visible as
incomplete audit rows and are excluded from sentinel processing.

The audit parses historical TEDANA metrics and mixing matrices, calculates
accepted/rejected counts and normalized variance fractions, and fits Motion24
to every steady-state ICA timecourse using OLS with an intercept. Motion24 is
limited to the six rigid-body parameters, their derivatives, their squares,
and squared derivatives. Only the expected initial derivative NaNs become
zero; any later nonfinite value is an error.

The builder requires the fMRIPrep derivative metadata to identify version
25.2.5 and requires the executable used for this audit to identify TEDANA
26.0.3. When historical TEDANA output metadata contains a version, it is
checked against that runtime. Because TEDANA metadata can be session-level
rather than run-level, `tedana_version_source` explicitly distinguishes a
metadata-derived value from the pinned-runtime fallback.

Outputs are:

```text
qc/tedana_audit/
  README.md
  current_runs.tsv
  summary_by_task.tsv
  sentinel_runs.tsv
  figures/
  report.md
  provenance.json

derivatives/tedana-audit/current/
  current_components.tsv
```

The tracked report is descriptive. It does not authorize a production change.

## Phase 2: Sentinel Benchmark

`benchmark_tedana.py` reads the algorithmically selected sentinel manifest and
writes every experimental derivative under:

```text
derivatives/tedana-audit/benchmark/<configuration>/<run-key>/
```

The four initial configurations are:

| Configuration | Purpose |
| --- | --- |
| `t2s-full` | TEDANA 26.0.3 `t2smap`, curvefit, all volumes used for estimation. |
| `t2s-exclude-nss` | Same command and fMRIPrep mask, with `--exclude 0:N`; all volumes remain in optcom. |
| `nss-fastica` | `--dummy-scans N`, curvefit, AIC, FastICA, seed 42, `tedana_orig`. |
| `nss-robustica` | Same, with RobustICA and an explicit 30 robust runs. |

Three additional configurations are intentionally opt-in:

| Configuration | Purpose |
| --- | --- |
| `full-fastica` | Exact AIC/FastICA match to `nss-fastica`, except `--dummy-scans 0`; this isolates the NSS effect. |
| `nss-kic-fastica` | Targeted NSS-aware KIC sensitivity condition. |
| `nss-mdl-fastica` | Targeted NSS-aware MDL sensitivity condition. |

The historical production-versus-`nss-fastica` comparison is not a clean NSS
experiment because production TEDANA did not receive the same explicit
fMRIPrep mask. Only `full-fastica` versus `nss-fastica` can be interpreted as
the effect of validated initial NSS removal.

`--jobs` controls run-level parallelism. T2* and FastICA jobs receive one thread.
`--robustica-threads` is passed to RobustICA as its internal `n_jobs` value so
its repeated ICA fits can run in parallel. Jobs are queued run-first, so the
requested configurations for a sentinel enter the queue together instead of
making RobustICA wait behind every FastICA run. Existing complete outputs are
skipped. An incomplete existing directory fails closed unless `--overwrite` is
explicitly supplied, and even then removal is confined to
`derivatives/tedana-audit`.

Every completed job has an `rf1_audit_provenance.json` recording its run,
configuration, exact command, NSS count, and original volume count. A resumable
run backfills missing provenance for otherwise complete outputs; the checker
validates those fields rather than accepting an unrecorded derivative.

The live run log prints `STARTED` when a worker launches a command and reports
its final status on completion. Near the end of a mixed benchmark, fewer than
`--jobs` processes may remain simply because only long RobustICA jobs are left.

Under the BIDS convention, pinned TEDANA 26.0.3 `t2smap` names the optimally
combined image `*_desc-optcom_bold.nii.gz` and the full T2* estimate
`*_T2starmap.nii.gz`. Completion checks use those registry names exactly.

Native NSS-aware TEDANA denoised output has `T-N` volumes. The runner creates a
separate audit-only full-grid image whose first `N` volumes come from the
full-length, native-space `t2s-full` benchmark optcom and whose remaining
volumes come from TEDANA. fMRIPrep does not retain a native-space non-echo
optcom in this dataset, and its MNI-space optcom cannot be combined with native
TEDANA output. The controlled TEDANA 26.0.3 `t2s-full` result is therefore the
appropriate grid-matched reference. Shape, affine, voxel sizes, TR, volume
counts, and both concatenated blocks are checked numerically. Event timing is
not shifted.

Each NSS-aware run also receives
`*_desc-ICA_mixingFullGrid.tsv`: exactly `N` zero rows followed by the native
TEDANA mixing matrix. The checker reconstructs that expected table and compares
every value. This is an audit artifact for evaluating future confound
construction; production `genTedanaConfounds.py` remains unchanged.

The optional `motion-fastica` and `motion-robustica` configurations are a later
audit pass. They dynamically copy the packaged 26.0.3 `tedana_orig` tree, add
Motion24 metric calculation, leave every decision node unchanged, and reuse the
completed mixing matrix. The checker requires classifications to remain exactly
identical to the corresponding ordinary NSS-aware run. Both supplied-matrix
commands set `--ica-method fastica` because TEDANA does not rerun ICA when
`--mix` is present, and TEDANA 26.0.3 otherwise attempts to report uninitialized
RobustICA diagnostics. `motion-robustica` still reuses the RobustICA matrix; the
FastICA argument is only a compatibility path for the metric-only pass.

## Linux2 Commands

Use the pinned TEDANA environment for both scripts:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
git pull --ff-only
umask 0000

AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python

"$AUDIT_PYTHON" audit_tedana.py build --dry-run

STAMP=tedana-cohort-audit-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" audit_tedana.py build --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" audit_tedana.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

Progress is printed every 100 runs. Generated tracked outputs are installed
atomically only after the complete scan succeeds, so `git status` remains clean
while the audit is running. The ignored raw log is live; the tracked compact
run record is written when `run_logged.sh` finishes.

Review `current_runs.tsv`, `sentinel_runs.tsv`, and `report.md` before starting
the expensive benchmark. Then validate the exact plan:

```bash
"$AUDIT_PYTHON" benchmark_tedana.py plan
```

Before the full benchmark, construct a four-run pilot spanning ordinary,
high-dimensional, and high-rejection cases with both zero and nonzero NSS:

```bash
PILOT=../logs/runlists/tedana-sentinel-pilot.tsv

awk -F $'\t' '
  NR == 1 ||
  $6 == "sub-10785_ses-01_task-sharedreward_run-1" ||
  $6 == "sub-11068_ses-01_task-sharedreward_run-1" ||
  $6 == "sub-11560_ses-01_task-doors_run-1" ||
  $6 == "sub-12008_ses-01_task-trust_run-2"
' ../qc/tedana_audit/sentinel_runs.tsv > "$PILOT"

wc -l "$PILOT"
# Expect 5: one header and four runs.

"$AUDIT_PYTHON" benchmark_tedana.py plan \
  --sentinel-tsv "$PILOT" \
  --configs t2s-full,t2s-exclude-nss,nss-fastica,nss-robustica
```

Launch all four controlled configurations for the pilot. This starts
RobustICA immediately without authorizing a production change:

```bash
STAMP=tedana-sentinel-pilot-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" -- \
    "$AUDIT_PYTHON" benchmark_tedana.py run \
      --sentinel-tsv "$PILOT" \
      --configs t2s-full,t2s-exclude-nss,nss-fastica,nss-robustica \
      --robustica-threads 4 \
      --jobs 4 \
    --check "$AUDIT_PYTHON" benchmark_tedana.py check \
      --sentinel-tsv "$PILOT" \
      --configs t2s-full,t2s-exclude-nss,nss-fastica,nss-robustica \
      --robustica-threads 4 \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

After that checker passes and resource use is acceptable, launch the same four
configurations for the full sentinel manifest. Completed pilot outputs skip;
no overwrite flag is used:

```bash
STAMP=tedana-sentinel-full-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" -- \
    "$AUDIT_PYTHON" benchmark_tedana.py run \
      --configs t2s-full,t2s-exclude-nss,nss-fastica,nss-robustica \
      --robustica-threads 4 \
      --jobs 8 \
    --check "$AUDIT_PYTHON" benchmark_tedana.py check \
      --configs t2s-full,t2s-exclude-nss,nss-fastica,nss-robustica \
      --robustica-threads 4 \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

Eight run-level jobs with four RobustICA workers each is a starting ceiling of
32 concurrent RobustICA workers, not a target to exceed. Monitor memory and
load before changing either level. Do not run the motion-audit configurations
until both corresponding NSS-aware
decompositions have completed. Do not run full-cohort RobustICA from this
workflow.

## Interpretation Gate

The initial benchmark is evidence gathering, not a production migration. Once
the four-configuration checker passes, build the paired interpretation outputs:

```bash
"$AUDIT_PYTHON" summarize_tedana_benchmark.py build --dry-run

STAMP=tedana-benchmark-summary-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      summarize_tedana_benchmark.py build --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      summarize_tedana_benchmark.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

The builder processes the 51 sentinels serially to keep memory predictable. It
writes nothing to the tracked output directory until every image pair and ICA
table has passed. The strict `NSS=0` controls must be numerically identical.
Tracked outputs under `qc/tedana_audit/benchmark/` include:

- `paired_t2s.tsv`: T2* and full-length optcom effects of excluding NSS from
  estimation, including raw, log-scale, rank, and voxelwise percent-difference
  comparisons so sparse extreme T2* fits do not control interpretation;
- `paired_ica.tsv`: historical, NSS-aware FastICA, and NSS-aware RobustICA
  decomposition summaries;
- `paired_denoising.tsv`: steady-state tSNR, variance removal, DVARS,
  FD-DVARS, Motion24 global-signal fit, and FastICA/RobustICA image similarity;
- `review_manifest.tsv`: high-priority rejected components and RobustICA
  index-quality warnings;
- `figures/`, `report.md`, and checksum/input provenance.

Review the paired tables, figures, and component manifest before launching the
optional motion-audit configurations. Only that reviewed evidence can recommend
changes to `tedana.sh`, `genTedanaConfounds.py`, the canonical TEDANA QC metric,
or an fMRIPrep issue. A successful checker does not authorize those changes or
a full-cohort RobustICA run.

## Motion24 Interpretation

After both `motion-fastica` and `motion-robustica` pass the combined checker,
build the component-level Motion24 interpretation outputs:

```bash
"$AUDIT_PYTHON" summarize_tedana_motion.py build --dry-run

STAMP=tedana-motion-summary-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      summarize_tedana_motion.py build --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      summarize_tedana_motion.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

The complete component table remains ignored at
`derivatives/tedana-audit/motion24_components.tsv`. Tracked outputs under
`qc/tedana_audit/motion/` include run/classification and task summaries, two
figures, a compact review manifest, a report, and checksum/input provenance.
The manifest selects each run/configuration's highest-motion accepted
component, lowest-motion rejected component, and largest-variance rejected
component, combining duplicate selections.

Counts above Motion24 R-squared values 0.10, 0.25, and 0.50 are descriptive.
They are not decision thresholds, and this stage cannot alter classification,
denoising, production TEDANA, or confound generation.

## Phase 3: Dimensionality And Design Burden

First run the matched full-volume FastICA condition for all 51 sentinels. It is
audit-only, uses one thread per job, skips complete outputs, and does not
overwrite prior configurations:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
git pull --ff-only
umask 0000
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python

"$AUDIT_PYTHON" benchmark_tedana.py plan \
  --configs full-fastica

STAMP=tedana-full-fastica-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" benchmark_tedana.py run \
      --configs full-fastica --jobs 8 \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" benchmark_tedana.py check \
      --configs full-fastica \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

The full-cohort design audit is independent of that rerun and may be launched
separately. It reads production files but writes only tracked audit summaries:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
mkdir -p ../logs/runs
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python

"$AUDIT_PYTHON" audit_tedana_design.py build --dry-run

STAMP=tedana-design-audit-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_design.py build --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_design.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

This audit reconstructs the exact output of `genTedanaConfounds.py`, compares
existing headerless TSVs, and reports nuisance rank with an intercept. Its
`residual_df_before_task` excludes task regressors and therefore overestimates
the residual degrees of freedom available in an L1 model. It also reads the
saved MAPCA JSON from each TEDANA run to compare AIC, KIC, and MDL dimensionality
without rerunning ICA.

After the `full-fastica` checker passes, build the matched sentinel summary:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
mkdir -p ../logs/runs
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python

"$AUDIT_PYTHON" summarize_tedana_dimensionality.py build --dry-run

STAMP=tedana-dimensionality-summary-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      summarize_tedana_dimensionality.py build --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      summarize_tedana_dimensionality.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

The checker requires every NSS=0 FULL/NSS FastICA pair to have byte-identical
metrics and numerically exact mixing matrices and denoised images. It also
requires FastICA and RobustICA to report identical PCA dimensionality before
comparing their final ICA counts.

Only after reviewing `qc/tedana_audit/design/pca_method_benchmark.tsv` should a
targeted PCA-method sensitivity run begin. Include `t2s-full` because it is the
validated full-grid reference for NSS-aware audit outputs:

```bash
TARGET=../qc/tedana_audit/design/pca_method_benchmark.tsv

"$AUDIT_PYTHON" benchmark_tedana.py plan \
  --sentinel-tsv "$TARGET" \
  --configs t2s-full,nss-fastica,nss-kic-fastica,nss-mdl-fastica

STAMP=tedana-pca-method-targeted-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" benchmark_tedana.py run \
      --sentinel-tsv "$TARGET" \
      --configs t2s-full,nss-fastica,nss-kic-fastica,nss-mdl-fastica \
      --jobs 8 \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" benchmark_tedana.py check \
      --sentinel-tsv "$TARGET" \
      --configs t2s-full,nss-fastica,nss-kic-fastica,nss-mdl-fastica \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

Do not launch this sensitivity run merely because the manifest exists. The
design report must first confirm that the selected cases and controls answer
the scientific question.

After all 80 targeted jobs validate, build the matched PCA-method summary:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
mkdir -p ../logs/runs
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python

"$AUDIT_PYTHON" summarize_tedana_pca_methods.py build --dry-run

STAMP=tedana-pca-method-summary-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      summarize_tedana_pca_methods.py build --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      summarize_tedana_pca_methods.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

The summary requires exactly identical optimally combined inputs across AIC,
KIC, and MDL. It compares model order, component classification, exact nuisance
rank, pre-task residual degrees of freedom, tSNR, DVARS, motion coupling, signal
scale, and denoised-image similarity. No single proxy is treated as ground
truth: higher tSNR or lower DVARS can also reflect over-aggressive signal
removal, while lower model order can merge distinct signal and noise sources.
Review the component manifest and task-model safety checks before any production
change.

## Upstream Evidence Gate

An upstream report must identify one mechanism at a time:

1. A material `full-fastica` versus `nss-fastica` effect supports discussion of
   fMRIPrep-to-TEDANA dummy-scan integration or documentation. Include the
   validated fMRIPrep NSS columns, exact commands, versions, and an anonymized
   minimal reproducer.
2. High AIC dimensionality with little matched NSS effect points toward MAPCA
   criterion behavior or scanner-era data properties, not an fMRIPrep NSS bug.
3. Fewer RobustICA components are a post-PCA stability result. They do not show
   that RobustICA repaired PCA.
4. A large confound column count is not enough. Report numerical rank, volumes,
   pre-task residual degrees of freedom, and the eventual task-design rank.

No public issue should contain private source paths, exclusion reasons, or
subject identifiers. Do not open an issue or propose a PR until the matched
summary and targeted method review agree on a reproducible failure mode.

## Phase 4: Final Decision Audit

This phase reflects the production RF1 model correctly. RF1 does not write an
aggressively denoised BOLD before task modeling. It fits task EVs, selected
fMRIPrep nuisance EVs, and rejected TEDANA IC timecourses simultaneously in the
same FEAT GLM. Accepted/rejected component overlap remains descriptive ICA QC;
the decision-facing tests are actual task/nuisance geometry and contrast
precision. No aggressive/non-aggressive/tedort comparison is part of this
phase, and no script writes a production residualized BOLD.

Run these stages sequentially on Linux2. The scanner-era and nuisance-QC stages
read large compressed images; do not overlap them merely to shorten wall time.

### 4A. Refresh cohort burden

The refreshed builder adds rejected fractions/variance, accepted-rejected
overlap, independent TEDANA rank cost, era/task/session quantiles, and p99
descriptive tails:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
git pull --ff-only
umask 0000
mkdir -p ../logs/runs

AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python

"$AUDIT_PYTHON" audit_tedana_design.py build --dry-run

STAMP=tedana-final-burden-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_design.py build --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_design.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

### 4B. Scanner-era forensic audit

The final raw-header pass requires `pydicom`. Do not use
`--skip-dicom-headers` for the decision report. Install the repository-pinned
additive dependency with `--no-deps` so pip cannot alter the working TEDANA
environment, then verify the environment before launching:

```bash
"$AUDIT_PYTHON" -m pip install --no-deps \
  -r ../requirements-tedana-audit.txt
"$AUDIT_PYTHON" -c 'import pydicom; print("pydicom", pydicom.__version__)'
"$AUDIT_PYTHON" -m pip check
"$AUDIT_PYTHON" audit_tedana_scanner_era.py build --dry-run

STAMP=tedana-scanner-era-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_scanner_era.py build --jobs 4 --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_scanner_era.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

Four workers are intentionally conservative because each run reads four
compressed echo series. The audit excludes identifiers, UIDs, dates, and
acquisition timestamps from tracked metadata. Raw-header output is restricted
to an explicit scientific-keyword allowlist; private tags, date/time VRs, UIDs,
person names, free-text fields, and representative DICOM paths are never
written to tracked tables. `protocol_exceptions.tsv` preserves run identities
only for prespecified scientific sidecar fields that vary within an era, so
legacy TR/flip-angle and phase-encoding exceptions can receive targeted review.
It cannot establish that a scanner-software change caused an observed
image-property difference.

### 4C. Nuisance-model QC

This uses the 51 sentinels and requires completed `full-fastica` and
`nss-fastica` outputs. Residual arrays exist only in memory:

```bash
"$AUDIT_PYTHON" audit_tedana_nuisance_qc.py build --dry-run

STAMP=tedana-nuisance-qc-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_nuisance_qc.py build --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_nuisance_qc.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

BASE versus TEDANA-FULL measures the incremental artifact-control proxy;
TEDANA-FULL versus TEDANA-NSS isolates NSS handling. All metrics use N:T, and
N=0 pairs must be numerically identical.

### 4D. Canonical first-level design geometry

The four downstream repositories must exist under `/ZPOOL/data/projects` and
their canonical activation FSFs must already have been rendered. This command
runs `feat_model`, not FEAT:

```bash
"$AUDIT_PYTHON" audit_tedana_l1_design.py build --dry-run

STAMP=tedana-l1-design-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_l1_design.py build --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_l1_design.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

The script fails if canonical FEAT temporal high-pass is enabled. It reports
task-EV nuisance R-squared/VIF, task-subspace overlap, rank/DF, condition, and
relative canonical contrast efficiency. It never evaluates whether a method
produces a larger desired activation.

### 4E. FastICA seed stability

Select and inspect the deterministic twelve-run manifest first:

```bash
"$AUDIT_PYTHON" audit_tedana_seed_stability.py select --dry-run
"$AUDIT_PYTHON" audit_tedana_seed_stability.py select --overwrite

SEEDS=../qc/tedana_audit/seeds/seed_runs.tsv
column -t -s $'\t' "$SEEDS" | less -S

"$AUDIT_PYTHON" benchmark_tedana.py plan \
  --sentinel-tsv "$SEEDS" \
  --configs t2s-full,nss-fastica-seed-1,nss-fastica-seed-10,nss-fastica-seed-42,nss-fastica-seed-100,nss-fastica-seed-1000
```

After review, run the 60 seed fits plus any missing T2S references:

```bash
STAMP=tedana-fastica-seeds-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" benchmark_tedana.py run \
      --sentinel-tsv "$SEEDS" \
      --configs t2s-full,nss-fastica-seed-1,nss-fastica-seed-10,nss-fastica-seed-42,nss-fastica-seed-100,nss-fastica-seed-1000 \
      --jobs 8 \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" benchmark_tedana.py check \
      --sentinel-tsv "$SEEDS" \
      --configs t2s-full,nss-fastica-seed-1,nss-fastica-seed-10,nss-fastica-seed-42,nss-fastica-seed-100,nss-fastica-seed-1000 \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

Then summarize classifications, nuisance rank, and adjusted-data stability
against seed 42:

```bash
STAMP=tedana-fastica-seed-summary-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_seed_stability.py build --overwrite \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
      audit_tedana_seed_stability.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

### 4F. Final synthesis

This command fails closed until every required table exists:

```bash
"$AUDIT_PYTHON" build_tedana_final_report.py build --dry-run

STAMP=tedana-final-report-$(date +%Y%m%d-%H%M%S)
bash run_logged.sh --label "$STAMP" --include-full-log -- \
  "$AUDIT_PYTHON" build_tedana_final_report.py build \
  --check "$AUDIT_PYTHON" build_tedana_final_report.py check
```

Review `qc/tedana_audit/final_report.md` and the targeted tables before any
production decision. A passing checker means the evidence package is complete;
it does not approve AIC/FastICA/NSS changes, alter Motion24's QC-only role, or
authorize an upstream issue.
