# 11935 Paired Initialization and Full Functional Validation

Isolated experiment, prepared October 22, 2026. No changes to production outputs,
canonical QC, exclusions, downstream models or the container image.

## Question and Design

Does the rigid coarse initialization from
https://github.com/nipreps/niworkflows/pull/1064 stabilize the preliminary N4 mask
and full post-SDC functional output for sub-11935 ses-01 Social Doors run 1?

1. Run the installed niworkflows 1.14.4 workflow on the original shortest-echo
   SBRef, with Affine[0.1] initialization versus Rigid[0.1]. Subsequent affine
   refinement remains unchanged. Everything else is identical within pairs.
2. Use five prespecified ANTs seeds: 20261021 through 20261025. Alternate which
   condition runs first. Fresh cache per condition/seed, one ANTs/OMP thread.
   These exercise stochastic registration; they do not guarantee bitwise
   reproducibility across hardware/ANTs versions or recover the historical seed.
3. Retain the initialization transforms, refinement commands/transforms, N4
   weight images, bias fields, enhanced references and masks. Save montages.
   Mask overlap with production is descriptive: pre-SDC versus post-SDC are
   not equivalent image stages. No overlap cutoff determines success.
4. Run two full functional pipelines sequentially, original then patched, using
   a prespecified fMRIPrep master seed of 20261021. It is not selected after
   inspecting the paired results. fMRIPrep derives its own ANTs seed from that
   master; that derived seed is equal between full-run conditions but need not
   equal the direct ANTs seed in the reference-only tests.

The full-run patch is an experiment-only bind-mounted copy of the installed
util.py with the single upstream scientific change. It does not upgrade other
dependencies.
Both full runs reuse anatomy-only derivatives and independent copies of
FreeSurfer. Neither can reuse old functional or fieldmap caches. Raw fieldmaps
remain available, with original IntendedFor metadata. Functional selection is
strictly subject 11935, session 01, Social Doors run 1, magnitude, all four echoes.

Original BIDS and production derivatives, TemplateFlow, and licenses are mounted
read-only. Outputs/caches are newly created under PROJECT/work. The script
refuses existing destinations and never renames/replaces production data.

Full processing includes motion/slice timing, fieldmap SDC, reference enhancement,
anatomical registration, multiecho combination and echo outputs, MNI/T1w
resampling, confounds and reports. CIFTI and surface-timeseries resampling are
omitted intentionally; FreeSurfer anatomy/registration remain enabled. TEDANA
and task GLMs are not part of this targeted fMRIPrep validation.

## Integrity and Acceptance

The full-run validator checks all data values in the four native echo series,
combined MNI/T1w series, 218-volume alignment, confound row count and required
motion columns, native echo-grid agreement, MNI qform/sform consistency, and the
production MNI grid. Coregistration Sources must include the original echo-1
SBRef and the matching Social Doors fieldmap coefficients. Actual full-workflow
antsAI commands must verify the assigned Affine/Rigid condition.

Canonical target-mask coverage is recomputed read-only, using the existing
compute_coverage function. No QC thresholds or decisions are changed. Native
post-SDC and MNI-mask montages plus registration/SDC reportlets must still be
reviewed. Technically passing output is not scientific acceptance or permission
to promote it. If the original full condition fails, the patched full condition
is still attempted; overall status remains failed until reviewed.

If both original and patched reruns look good across all five seeds and the full
run, that establishes reproducible recovery under these tested settings, not
proof that the patch caused recovery or that the historical failure was fixed.
If only the patched condition consistently restores the mask and full output,
that is stronger evidence for this known initialization failure. Any downstream
repair/promotion is a separate, explicitly reviewed step.

## Launch

The self-contained runner is tracked at `code/run_11935_initialization.py`.
Pull this repository normally; no SCP of code, pip install, or image rebuild is needed.

### Continue the completed October 22 reference tests

The `11935-init-test-20261022-095859` record completed all ten reference
conditions. Both full runs stopped during configuration initialization, before
functional processing. The experiment-generated filter used numeric `run: 1`;
fMRIPrep 25.2.5 checks string membership while rehydrating that value and raises
`TypeError`. This is not a BIDS image problem or a change to the canonical
`code/fmriprep_config.json`. The runner now serializes the same run selector as
the string `"1"` for compatibility.

Reuse the completed reference evidence with a NEW output directory:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
SOURCE="$PWD/work/11935-init-test-20261022-095859"
STAMP=11935-init-test-$(date +%Y%m%d-%H%M%S)
OUT="$PWD/work/$STAMP"
python3 code/run_11935_initialization.py --output "$OUT" \
  --reuse-reference-test "$SOURCE" --dry-run
```

After that preview succeeds, in the same shell:

```bash
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 python3 code/run_11935_initialization.py \
    --output "$OUT" --reuse-reference-test "$SOURCE" --nprocs 8 \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "Results: $OUT"
tail -f "logs/runs/${STAMP}.nohup.out"
```

Reuse checks the ten expected completed conditions, saved evidence checksums,
current input checksums, exact patch, and container source/versions. It copies
reference evidence into the new experiment, leaves the old package untouched,
and launches only the two full functional comparisons with fresh caches and
independent FreeSurfer copies. It does not infer that the reference masks are
scientifically acceptable merely because the conditions completed.

### Start a new experiment including all reference tests

On Linux2, from the repository root:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
mkdir -p logs/runs
STAMP=11935-init-test-$(date +%Y%m%d-%H%M%S)
OUT="$PWD/work/$STAMP"
RUNNER="$PWD/code/run_11935_initialization.py"
python3 "$RUNNER" --output "$OUT" --dry-run
```

Stop if the pull or preview fails. After the preview succeeds, launch in the
same shell:

```bash
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 python3 "$RUNNER" --output "$OUT" --nprocs 8 \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "OUT=$OUT"
tail -f "logs/runs/${STAMP}.nohup.out"
```

Eight total processes for one full run at a time, OMP one, 24 GB fMRIPrep
scheduler memory budget. Reference tests are sequential/single-threaded. Existing
cohort TEDANA and L1/L2 jobs are not touched. The memory setting is a scheduler
budget, not an operating-system hard limit.

Expect a nontrivial FreeSurfer staging copy before the first container
stage. There is no reliable runtime estimate before executing on Linux2.

## Results

- OUT/state.json: overall completion, technical validation and source preservation.
- OUT/paired-results.json, paired-comparison.json and paired-stability.json:
  five paired outcomes and descriptive across-seed mask stability.
- OUT/full-{affine,rigid}-validation.json: temporal/echo/grid checks and coverage.
- OUT/index.html: paired images and full post-SDC/MNI comparisons.
- OUT/patch/provenance.json: exact source hashes, versions, patch and module path.
- OUT/full/{affine,rigid}/derivatives: complete isolated volumetric outputs.
- OUT.tar.gz: transferable evidence, reports, 3D references/masks, confounds and
  hashes. Full 4D outputs, anatomy, FreeSurfer and caches stay on Linux2.

Generated experiment outputs remain under ignored `work/`, consistent with the
repository's BIDS/derivative artifact layout. Code, tests, and this runbook are
version-controlled. A run record alone is not enough for scientific/visual
validation: download and inspect the evidence archive.

Local tests exercise patch bounds, command/filter isolation, copying rather than
linking, refusal to overwrite, archive exclusions, failure handling, source-change
detection and image integrity. Actual Nipype/ANTs/fMRIPrep integration is not
available on the Mac and remains the purpose of the Linux2 execution.
