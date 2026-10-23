# Complete The 11935 Repair

## Scope And Evidence

This is a two-acquisition functional repair, not a cohort upgrade. Keep the
existing fMRIPrep 25.2.5 image and bind the exact, hash-checked niworkflows
`init_aff` Affine-to-Rigid backport tested in the paired-seed experiment. The
subsequent affine refinement is unchanged. No fMRIPrep fork or global image
replacement is needed. The official change is
[niworkflows #1064](https://github.com/nipreps/niworkflows/pull/1064).

Both experimental full runs recovered the historical mask defect (original
99.59%, rigid 99.43%, historical 77.98%). Original reference initialization
misplaced the N4 prior in seeds 20261022/20261024; rigid avoided that in all five
tested seeds. This supports improved stability, not proof that only the patch
can recover the historical failure or that every dataset/seed is fixed.

Do not transplant the historical-label experimental BOLD into corrected Faces.
Use the approved source mapping: Faces/Social Doors 25/26 with SBRef23;
Doors 29/30 with SBRef27. Both are 218-volume runs. A previous Doors run may be
absent entirely, so installing the repair can legitimately add that run.

`complete_11935_repair.py` converts in isolation, retains unrelated conversion
products outside the staged dataset, and rebuilds only these two functional
runs. It reuses anatomy and independent completed FreeSurfer copies. WarpKit,
MRIQC, HMC, SDC, BOLD-to-anatomy registration, MNI/surface resampling, motion
parameters, FD, CompCor, production TEDANA and combined confounds are rebuilt.
Raw behavioral files, other tasks/sessions, anatomy and other participants are
not changed. `RF1Repair` in the promoted fMRIPrep sidecars records the image
and patch hashes, seed and approved source mapping.

Motion estimation is not simply the broken masking node. Nevertheless, fresh
two-run functional caches prevent old transforms/confounds from being carried
across corrected task labels. The separate motion-parameter reconstruction
change in [25.2.7](https://github.com/nipreps/fmriprep/releases/tag/25.2.7)
is NOT backported here. This retains the cohort's 25.2.5 processing conventions;
it does not claim to implement every 25.2.7 fix or require reprocessing everyone.

## Stage Without Interrupting Production

Run on Linux2. The runner uses the current approved behavior and source roots.
Use a fresh workspace after an intentional runner/code revision; never bypass
the frozen receipts. Complete checked stages are preserved on ordinary resume.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
umask 0000
export AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
export REPAIR_DIR="$PWD/work/11935-final-repair-v1"
export SOCDOORS_ROOT=/ZPOOL/data/projects/rf1-sra-socdoors
export COHORT_ROOT="$PWD/derivatives/tedana-audit/cohort-pca-v1"
STAMP=11935-final-stage-$(date +%Y%m%d-%H%M%S)
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 bash code/run_11935_completion.sh stage \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "STAMP=$STAMP"
tail -30 "logs/runs/${STAMP}.nohup.out"
```

Expect both corrected runs staged through confounds, unchanged production,
and `work/11935-final-repair-v1/11935-repair-review.tar.gz`. Inspect all four
native/MNI montages and functional-validation.json before approval. The new
Faces acquisition and its matched reference need their own validation, even
though the historical acquisition already recovered in the experiment.

## Pause The Benchmark If Still Running

Promotion refuses an active cohort, fMRIPrep subject job or task-model runner.
Do not delete locks. Finish existing L1/L2 jobs before installation. If the
cohort runner is still active, identify its exact Python PID:

```bash
ps -u "$USER" -o pid,comm,args |
  awk '$2 ~ /^python/ && /benchmark_tedana_cohort.py run/ {print}'
```

The helper automatically identifies one matching Python runner, or accepts
`--pid NUMBER` to select the exact PID printed above. The preview checks the exact runner,
explicit audit root, owner and separate run_logged session. The apply command
terminates only that session, retains verified successes and archives partial
attempts. In-flight attempts must run again; completed successes do not. This
does not stop separate L1/L2 jobs. If no runner is active, omit this block.

```bash
"$AUDIT_PYTHON" code/pause_tedana_cohort.py --project-root "$PWD" \
  --audit-root "$COHORT_ROOT"
"$AUDIT_PYTHON" code/pause_tedana_cohort.py --project-root "$PWD" \
  --audit-root "$COHORT_ROOT" --apply
```

## Install Reviewed Products

After reviewing the new corrected images, install at the ordinary paths. Old
bytes, stale model outputs and original cohort input files are archived under
`REPAIR_DIR/replaced-originals/`, with strong hashes and a durable transaction
receipt. Nothing is silently overwritten or relabeled into a new analysis.

```bash
bash code/run_logged.sh --label "11935-promote-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- env PYTHONUNBUFFERED=1 \
  bash code/run_11935_completion.sh promote --approve-images
```

This also explicitly retires/versions the old cohort manifest and affected
method outputs, then freezes the corrected two rows. Unrelated rows/receipts
are preserved. It can add the previously absent Doors row. Interrupted
installation/revision fails closed: preserve the receipt/archive/temporaries
and inspect before recovery; do not delete them or rerun promotion blindly.
Do not rerun the old isolated stage checker after promotion: its protected
production-input receipt is intentionally historical by then.

## Rebuild Models And Resume Variants

The following rebuilds both activation L1s and the canonical paired-mean L2
under each of `rf1-sra-socdoors/derivatives/fsl` (production TEDANA nuisance)
and `derivatives/fsl-no-tedana-age55` (fMRIPrep-only nuisance; age >=55 from
participants.tsv). It regenerates canonical EVs, refreshes/checks QC within
exact task/session strata, refreshes the baseline production TEDANA inventory,
and emits subject-only technical manifests. Historical sentinel benchmarks
remain preserved studies, not newly rerun experiments. The active cohort PCA
comparison is revised and resumed separately below.

```bash
STAMP=11935-models-qc-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 FSLSUB_PARALLEL=1 \
  bash code/run_11935_completion.sh finish \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &

STAMP=tedana-cohort-post-11935-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 COHORT_JOBS=20 \
  bash code/run_11935_completion.sh variants \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
```

The ordinary cohort runner queues the full revised manifest, skips valid
completed jobs, and runs the six repaired run/method combinations plus any
other unfinished jobs. It rebuilds/checks AIC, KIC and MDL summaries when done;
do not claim that exactly six jobs will execute if other jobs were pending.
No replacement production PCA criterion is selected.

## Handoff And Remaining Analyses

Canonical downstream BOLD/confound/EV/L1/L2 filenames do not change. The new
products become the live inputs; archives serve provenance only. Read
`REPAIR_DIR/models/subject_ready.tsv`, `models/completion.json`, technical-L1.tsv,
technical-L2.tsv, current canonical QC and the cohort validation.json. Models
can finish independently of the remaining cohort experiment.

Stale seed/network PPI products discovered during promotion are archived and
listed as requiring their own rebuild; this activation runner never pretends
to recreate those models. Similarly, group/L3 inputs, ROI extractions and
group models containing old products must be regenerated by their owning
analysis. No L3 is run automatically and no new paper N is claimed.

Source exclusions, task holds and reviewed dispositions remain authoritative.
QC flags are recomputed descriptions, not automatic new exclusion decisions.
Previously frozen paper handoffs remain historical; Jacob must refresh the
affected paper selection/group inputs after accepting the repaired products.
