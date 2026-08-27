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

TEDANA itself receives one thread per run; `--jobs` controls run-level
parallelism. Existing complete outputs are skipped. An incomplete existing
directory fails closed unless `--overwrite` is explicitly supplied, and even
then removal is confined to `derivatives/tedana-audit`.

Native NSS-aware TEDANA denoised output has `T-N` volumes. The runner creates a
separate audit-only full-grid image whose first `N` volumes come from the
full-length fMRIPrep optcom and whose remaining volumes come from TEDANA. Shape,
affine, voxel sizes, TR, volume counts, and both concatenated blocks are checked
numerically. Event timing is not shifted.

Each NSS-aware run also receives
`*_desc-ICA_mixingFullGrid.tsv`: exactly `N` zero rows followed by the native
TEDANA mixing matrix. The checker reconstructs that expected table and compares
every value. This is an audit artifact for evaluating future confound
construction; production `genTedanaConfounds.py` remains unchanged.

The optional `motion-fastica` and `motion-robustica` configurations are a later
audit pass. They dynamically copy the packaged 26.0.3 `tedana_orig` tree, add
Motion24 metric calculation, leave every decision node unchanged, and reuse the
completed mixing matrix. The checker requires classifications to remain exactly
identical to the corresponding ordinary NSS-aware run.

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
    "$AUDIT_PYTHON" audit_tedana.py build --overwrite \
    --check "$AUDIT_PYTHON" audit_tedana.py check \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

Review `current_runs.tsv`, `sentinel_runs.tsv`, and `report.md` before starting
the expensive benchmark. Then validate the exact plan:

```bash
"$AUDIT_PYTHON" benchmark_tedana.py plan
```

The recommended first benchmark launch is conservative:

```bash
STAMP=tedana-sentinel-initial-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" -- \
    "$AUDIT_PYTHON" benchmark_tedana.py run \
      --configs t2s-full,t2s-exclude-nss,nss-fastica \
      --jobs 2 \
    --check "$AUDIT_PYTHON" benchmark_tedana.py check \
      --configs t2s-full,t2s-exclude-nss,nss-fastica \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

Launch RobustICA separately after the first wave has passed and resource use is
understood:

```bash
STAMP=tedana-sentinel-robustica-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w \
  bash run_logged.sh --label "$STAMP" -- \
    "$AUDIT_PYTHON" benchmark_tedana.py run \
      --configs nss-robustica \
      --jobs 2 \
    --check "$AUDIT_PYTHON" benchmark_tedana.py check \
      --configs nss-robustica \
  > "../logs/runs/${STAMP}.nohup.out" 2>&1 &
```

Do not run the motion-audit configurations until both corresponding NSS-aware
decompositions have completed. Do not run full-cohort RobustICA from this
workflow.

## Interpretation Gate

The initial benchmark is evidence gathering, not a production migration. After
it completes, the next code pass will calculate paired T2*/optcom effects,
FastICA-versus-RobustICA summaries, denoising metrics, and the focused component
review manifest. Only that reviewed report can recommend changes to
`tedana.sh`, `genTedanaConfounds.py`, the canonical TEDANA QC metric, or an
fMRIPrep issue.
