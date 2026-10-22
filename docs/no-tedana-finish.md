# Finish baseline age-55+ activation without TEDANA nuisance ICs

This follow-up preserves the completed original batch and its frozen scripts.
It does not change the running cohort TEDANA experiment, production confounds,
existing FEAT outputs, QC thresholds, or settled source-validity decisions.

## Scope and outputs

- Age >=55 from `bids/participants.tsv`, ses-01 activation only.
- Reverify and reuse the original UGR/Social Doors L1 jobs byte-for-byte.
- Add nonsocial `doors` run 1, using its own BOLD, events, EVs and QC rows.
- Retry previously omitted technically eligible L1s. Unlike the original batch,
  available aCompCor columns 00-05 are selected as in production; six are not
  mandatory. At least column 00, all motion columns and FD remain required.
  Cosine/NSS columns and zero-filling of missing values are unchanged. No ICA
  columns are added, and task/nuisance regressors are fitted simultaneously.
- Generate canonical UGR fixed-effects means for participants with both runs.
- Generate canonical Social Doors + Doors fixed-effects means when both tasks
  are available. The existing template is a **mean**, NOT social-minus-doors.
- Preserve each task/run's independent L1 output even when the other is absent.

Outputs remain in each task repository's `derivatives/fsl-no-tedana-age55/`.
No old TEDANA-based L2 output is used. Both the new and original runner use the
same output-root locks, inherited by subprocesses. An existing unowned,
partial or changed output stops that job; nothing is overwritten automatically.
Do not update frozen scripts/inputs while either batch is running.

The original `run_no_tedana_l1.py` and its dependencies are intentionally not
edited. `finish_no_tedana.py` verifies the parent plan, signatures, completed
outputs and current age/source/disposition gates. A changed parent eligibility
decision fails preparation rather than silently importing an old run.

## Linux2: prepare

Use the FSL-enabled shell and the same account as the completed batch. Run this
block first; review `run_review.tsv` and the new/held/missing counts before launch.
Paths and per-run details stay under ignored `work/`; do not commit them.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
export AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NO_TEDANA_FINISH="$PWD/work/no-tedana-finish-$(date +%Y%m%d-%H%M%S)"
PARENT="$PWD/work/no-tedana-age55-20261021-111205"
DECISIONS=()
if [[ -f qc/run_disposition.tsv ]]; then
  DECISIONS=(--dispositions "$PWD/qc/run_disposition.tsv")
fi
command -v feat feat_model fslnvols
bash code/run_logged.sh --label "no-tedana-finish-prepare-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- "$AUDIT_PYTHON" code/finish_no_tedana.py prepare \
  --parent-dir "$PARENT" --private-dir "$NO_TEDANA_FINISH" "${DECISIONS[@]}"
echo "Private plan: $NO_TEDANA_FINISH"
```

Stop after a failed pull, missing FSL executable, or nonzero preparation exit.
If reviewed dispositions live elsewhere, supply that explicit path. Preparation
success is not a claim that every expected run is available: missing/invalid
and held rows remain in the review table. No QC flag determines preparation.

## Linux2: run and check

Use the same shell/private directory. Four workers is the initial concurrency
while the separate TEDANA experiment runs; measure memory/I/O before increasing.
Each FEAT job has local fsl_sub and BLAS/OpenMP pools limited to one.

```bash
STAMP=no-tedana-finish-$(date +%Y%m%d-%H%M%S)
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 FSLSUB_PARALLEL=1 \
    "$AUDIT_PYTHON" code/finish_no_tedana.py run \
    --private-dir "$NO_TEDANA_FINISH" --jobs 4 \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "Private plan: $NO_TEDANA_FINISH"
echo "Log: logs/runs/${STAMP}.nohup.out"
```

The runner does L1 then L2 then verification; a failed L1 stage prevents L2.
It writes `l1-status.json`, `l2-status.json`, per-run logs, and only after a
successful final check, `handoff_candidates.tsv`. `--timeout` (default 7200s)
limits waiting for L2 products after the FEAT command returns. Structural checks
include every canonical cope/varcope/zstat, mask, DOF, design and lineage; this
is not visual QC or proof of model validity. L2 inputs are verified L1s from
this variant, with frozen registration/DOF metadata and successful output records.

To recheck or resume, reuse the printed private path (do not prepare a new plan):

```bash
"$AUDIT_PYTHON" code/finish_no_tedana.py check --private-dir "$NO_TEDANA_FINISH"
# Only after checking no previous runner/child FEAT jobs remain:
"$AUDIT_PYTHON" code/finish_no_tedana.py run --private-dir "$NO_TEDANA_FINISH" --jobs 4
```

Completed owned outputs are verified and skipped. Failed/partial outputs need
inspection and explicit archival before retry; the runner never deletes them.

### Changing concurrency on Linux2

Do not start a duplicate runner or kill all FEAT processes. For a run launched
with the isolated `setsid` command above, use `code/restart_no_tedana_finish.py`
with the exact Python runner PID and the existing private plan. First preview:

```bash
"$AUDIT_PYTHON" code/restart_no_tedana_finish.py \
  --pid "$RUNNER_PID" --private-dir "$NO_TEDANA_FINISH"
# Only after preview succeeds:
"$AUDIT_PYTHON" code/restart_no_tedana_finish.py \
  --pid "$RUNNER_PID" --private-dir "$NO_TEDANA_FINISH" --apply
```

The helper freezes and terminates only that isolated logged session, refuses
escaped children or a shared interactive session, and waits for termination.
It then acquires the same output locks, verifies the frozen plan and successful
products, and moves unmarked partial FEAT outputs into each isolated derivative
root's `restart-archives/` folder. No outputs are deleted. Reused parent outputs
and valid success records are preserved. Invalid recorded successes stop recovery
rather than being silently regenerated. A private restart JSON records each move.
The interrupted original log may lack a final footer; keep it with the restart
record as provenance. This helper does not modify frozen runner code.

Only after `RESTART READY`, launch the original logged `run` command with the same
private directory and `--jobs 20`. Do not rerun `prepare`. If the old runner has
already exited, or any recovery step fails, inspect before proceeding; do not
substitute another PID. Twenty workers are a ceiling, not a memory guarantee.

## Handoff, not an automatic L3 cohort

**2026-10-21 paper decision:** use the separate
[coverage95 handoff](coverage95-paper-handoff.md) after this runner completes.
It applies the PI-approved run-level coverage cutoff, preserves good single
runs and settled decisions, and exports selected inputs without changing this
frozen runner or its candidate table. Boxplot flags remain descriptive.

`handoff_candidates.tsv` lists contrast-specific cope/varcope/mask/DOF and FEAT
paths. `run_review.tsv` contains task/session/run-specific flags and decisions.
The candidate table deliberately includes alternatives. It must NOT be fed
directly into L3 as though every row were an independent participant.

- For UGR, choose exactly one approved run subset per participant and contrast:
  paired-run L2 only if both constituent runs are eligible, otherwise the eligible
  run's L1. A rejected run cannot enter through a precomputed paired L2.
- Social Doors and Doors L1s are independently eligible. Requiring the paired
  mean must not exclude someone from a single-task analysis.
- Use paired Social Doors/Doors L2 only for an explicitly intended combined-mean
  analysis and only when both constituent tasks are eligible.
- QC flags are not decisions. Source exclusions, explicit run holds and supplied
  reviewed dispositions still apply. Session 02 has no bearing on this batch.
- Reconcile the paper's screener-age/survey/environmental cohort with the batch's
  imaging-age >=55 gate. This runner does not claim final paper Ns or run L3.

## Coverage versus rejected components: current descriptive evidence

The October 21 canonical QC/scanner-era data have 2781 matched run rows. The
earlier correlation inputs were reverified unchanged when preparing this follow-up.
Within baseline task, Spearman coverage/rejected-count correlations and correlations
of ranked values residualized on an intercept plus categorical era indicators are:

| ses-01 task | Runs | Spearman | Era-adjusted ranked correlation |
|---|---:|---:|---:|
| UGR | 660 | -0.400 | +0.085 |
| Social Doors | 337 | -0.423 | +0.044 |
| Doors | 337 | -0.405 | +0.052 |

For baseline Social Doors, E11 median target coverage/rejected count is
99.864%/10 versus XA60 99.560%/22. Within-era Spearman correlations are +0.052
(E11), -0.060 (XA30, only 17 runs), and +0.059 (XA60). Thus the pooled baseline
association is largely a between-era pattern, not evidence that losing coverage
causes more rejected components. Era also tracks acquisition/cohort history;
this adjustment does not prove scanner software is the cause.

Do not generalize this to wave 2: ses-02 adjusted correlations remain negative
(UGR -0.362, Social Doors -0.499, Doors -0.253; 63/32/32 runs, almost all XA60).
Repeated UGR runs are not independent subjects; these are descriptive effect
sizes without causal claims or independent-run significance tests.

Coverage is an overlap of the fMRIPrep MNI mask with a fixed reference excluding
historical cerebellum/brainstem regions; it is not TEDANA's adaptive mask and is
not recomputed from rejected ICs. Smaller masks, dropout, motion or registration
differences can have shared causes with decomposition/classification changes,
but those mechanisms have not been established here. TEDANA documents that
adaptive masking depends on good echoes and initial-mask quality:
https://tedana.readthedocs.io/en/latest/approach.html

Next mechanistic checks should compare spatial missing-coverage maps, native
mask/adaptive-good-echo masks, acquisition parameters and decomposition size
within each task/session/era. Neither lowering IC counts nor dropping IC nuisance
columns will repair a coverage problem or by itself demonstrate better denoising.
