# Age-55+ baseline activation without TEDANA nuisance ICs

The PI requested this separate analysis for the Katie/Sophia work, using age
**>=55 from `bids/participants.tsv`**, session **01**, UGR runs 1/2 and Social
Doors run 1. This is not the survey-linked paper cohort and does not claim a
final L3 N. Participants.tsv records baseline imaging age, not necessarily the
age at screener administration. Missing ages are reported, never imputed.

## Model and selection

`code/run_no_tedana_l1.py` retains the full-length fMRIPrep MNI BOLD, canonical
task EV files, task models (UGR model 3, Social Doors model 1), smoothing and
contrasts. It constructs a new headerless confound matrix directly from the
fMRIPrep TSV, selecting the same production base columns in the same order:

- `a_comp_cor_00` through `a_comp_cor_05`;
- `trans_x/y/z`, `rot_x/y/z`, `framewise_displacement`;
- all `cosine*` and `non_steady_state*` columns present in that run.

Missing numeric values are filled with zero as in production. All 13 fixed
base columns are required; malformed/nonfinite data and row mismatches fail.
No rejected ICA timecourses are added. No BOLD residualization is performed:
task and nuisance regressors remain simultaneous in the FEAT GLM. This is a
specific alternative nuisance model, not proof that TEDANA is ineffective.

The existing source-exclusion, run-hold and optional reviewed-disposition
contracts remain enforced. QC flags are copied to the review table but **none
is an automatic selection criterion**, including TEDANA component-count flags.
No flags, thresholds, original manifests or settled exclusions are rewritten.
Source-invalid runs do not become valid by omitting TEDANA. One available UGR
run is allowed independently of the other; session 02 never affects session 01.

The technical inventory is rebuilt using the established availability audit,
but readiness is re-evaluated with the replacement base-only confounds. Missing
TEDANA mixing/metrics or old combined confounds do not themselves block a run.
The upstream audit's existing live roots/QC tables must still be available.

## Isolation and provenance

New FEAT outputs live in each task repository at:

```
derivatives/fsl-no-tedana-age55/sub-XXXXX/ses-01/
```

Canonical task EVs remain under `derivatives/fsl/EVfiles/`. The small downstream
`EV_FILES_ROOT` override allows those EVs to be reused without copying or
rewriting them, while `FSL_DERIVATIVES_ROOT` isolates rendered designs and FEAT
products. Defaults for ordinary L1stats calls are unchanged.

The private batch directory contains `plan.json`, `run_review.tsv`, new
`confounds/`, per-run `logs/`, command-status JSONs and, after verification,
`completed_runs.tsv`. No participant-level outputs should be committed.
The plan freezes age/roster/QC/decision inputs, exclusions, EVs, scripts and
templates. Text inputs use SHA256 plus file metadata; large NIfTI inputs use
path/size/mtime rather than a full cryptographic content hash.

Each run renders its canonical FSF, checks exact BOLD/confound/output paths,
and runs `feat_model` with the base-only confound matrix before FEAT. It requires
finite designs, correct rows and canonical contrast counts, estimable contrasts
and positive unwhitened residual degrees of freedom. Optional zero-valued miss
EVs are permitted; full column rank is not required when contrasts are estimable.

Completion checks require all canonical cope/varcope/zstat products, mask and
design files, plus unchanged input signatures and a matching success record.
These are structural/lineage checks, not visual QC or proof of scientific
validity. Successful same-plan outputs are verified and skipped on resume.
Partial, unowned or modified outputs are never automatically deleted or
overwritten. Locks prevent multiple plans concurrently writing the same variant
roots. To retry a failed partial FEAT directory, first inspect and explicitly
archive it; do not use the canonical `--overwrite` workflow on this batch.

## Linux2 commands

Use an FSL-enabled shell. Run the first block and review the per-task ready,
held, under-55, unknown-age and missing/invalid counts before launching.

```bash
for repo in rf1-sra-linux2 rf1-sra-ugr rf1-sra-socdoors; do
  git -C "/ZPOOL/data/projects/$repo" pull --ff-only || break
done
cd /ZPOOL/data/projects/rf1-sra-linux2
export AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NO_TEDANA="$PWD/work/no-tedana-age55-$(date +%Y%m%d-%H%M%S)"
command -v feat feat_model fslnvols
DECISIONS=()
if [[ -f qc/run_disposition.tsv ]]; then
  DECISIONS=(--dispositions "$PWD/qc/run_disposition.tsv")
fi
bash code/run_logged.sh --label "no-tedana-age55-prepare-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- "$AUDIT_PYTHON" code/run_no_tedana_l1.py prepare \
  --private-dir "$NO_TEDANA" "${DECISIONS[@]}"
```

If reviewed dispositions live elsewhere, supply that file explicitly instead.
Do not proceed after a failed pull, preparation or missing FSL command. A
successful prepare does not assert that all expected runs are ready: inspect
`run_review.tsv` for every omitted unit. The launcher attempts only ready units.

```bash
STAMP=no-tedana-age55-L1-$(date +%Y%m%d-%H%M%S)
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 FSLSUB_PARALLEL=1 \
    "$AUDIT_PYTHON" code/run_no_tedana_l1.py run \
    --private-dir "$NO_TEDANA" --jobs 4 \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "Private batch: $NO_TEDANA"
echo "Log: logs/runs/${STAMP}.nohup.out"
```

Start with four FEAT workers while the 40-job TEDANA experiment runs. These
are different workloads; FEAT launches several processing stages. The runner
sets BLAS/OpenMP and the local fsl_sub pool to one per worker. Measure memory
and I/O before increasing concurrency. Run time cannot be guaranteed in advance.

`run` performs the final `check` automatically. To recheck or resume, use the
same directory (do not generate a new timestamp):

```bash
"$AUDIT_PYTHON" code/run_no_tedana_l1.py check --private-dir "$NO_TEDANA"
# Resume verified successes and attempt only missing outputs:
"$AUDIT_PYTHON" code/run_no_tedana_l1.py run --private-dir "$NO_TEDANA" --jobs 4
```

`render` is also available instead of `run` for a design-only preflight.

## Handoff boundary

Do not point Jacob at these paths until the Linux2 completion check passes.
This runner performs L1 only. Existing UGR L2 fixed-effects and all L3 outputs
still belong to their old nuisance model. UGR needs a separate, isolated
L2/single-run handoff before paper L3 inputs are updated. Do not combine old
TEDANA and new base-only runs, reuse old L2 outputs, or require two runs merely
because the paired-run L2 template expects two. Social Doors here means the
`socialdoors` task only, not the separate nonsocial `doors` task or their L2
difference model. Other analysis/QC decisions remain explicit and task/session
specific.
