# XA60 coverage: private paired image inspection

This is a read-only diagnostic package, not a new QC rule or an exclusion list.
It does not modify source/BIDS/derivative images, run_qc.tsv, thresholds, task
manifests or prior decisions. It can run while TEDANA/FEAT are working, with
limited parallelism to reduce shared disk and memory load.

## Comparison set

Defaults: all canonical XA60 coverage-flagged ses-01 runs for UGR, Social Doors
and Doors, not just an age-selected or survey-linked cohort. On the October 21
snapshot this selects 66 flagged runs, 132 pairings and 176 distinct image runs.
Each case has up to two controls from different participants, matched exactly
on XA60, task, session and run number, ordered by nearest mean FD. Controls pass
**coverage only** and have complete QC metrics; other flags remain visible.
TEDANA counts do not determine control selection. Controls may be reused across
cases. Pairings are descriptive, not independent statistical observations.

`--sessions 01,02` includes wave 2 but still matches within session. Default is
01 because this investigation began with the baseline paper exclusions.
`--max-cases 3` makes a pilot of the three lowest-coverage cases. The same-task
passing pool remains available even when the case list is restricted.

## Linux2 commands

No new dependencies are expected in the TEDANA Python environment: numpy,
nibabel, scipy, pandas and matplotlib are required. This script uses no DICOM parsing,
downloads or external image services. Start with two workers while other jobs
are running. Three separated volumes from each BOLD file are read, not a full
4D array; gzip reads can still be I/O intensive.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
export AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export COVERAGE_REVIEW="$PWD/work/xa60-coverage-$(date +%Y%m%d-%H%M%S)"
"$AUDIT_PYTHON" -c 'import numpy, nibabel, scipy, pandas, matplotlib; print("Inspection dependencies available")'
"$AUDIT_PYTHON" code/inspect_xa60_coverage.py build \
  --private-dir "$COVERAGE_REVIEW" --sessions 01 --dry-run
```

Stop if the pull, dependency check or dry run fails. After reviewing counts,
launch in the same shell:

```bash
STAMP=xa60-coverage-$(date +%Y%m%d-%H%M%S)
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/inspect_xa60_coverage.py build \
    --private-dir "$COVERAGE_REVIEW" --sessions 01 --jobs 2 \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "Private report: $COVERAGE_REVIEW/index.html"
echo "Log: logs/runs/${STAMP}.nohup.out"
```

The build runs its verification automatically. Recheck with:

```bash
"$AUDIT_PYTHON" code/inspect_xa60_coverage.py check --private-dir "$COVERAGE_REVIEW"
```

No overwrite or resume is performed. If inspection fails, review the private
error details; existing images and prior packages are preserved. Use a new
directory after fixing the cause, or a restricted pilot before a full rerun.

## Outputs and privacy

The package is under ignored `work/`, with a mode-0700 top-level directory:

- `index.html` and one linked comparison page per flagged case;
- `pairs.tsv`, including FD gaps and any missing control;
- `run_inventory.tsv`, including each run's original QC metrics and flags;
- `measurements.tsv`, with recomputed coverage, fixed-reference coverage and
  descriptive signal values in target voxels outside the fMRIPrep mask;
- per-run MNI, native and original-BIDS PNGs, sampled 3D NIfTIs, and `evidence.json`;
- `manifest.json`, recording inputs, image size/mtime, output hashes and errors.

Open `index.html` in a browser on a machine that can access the directory, or
transfer the whole directory privately to your workstation. Keep paths together
so relative image links work. No web server or public upload is necessary.
Do not commit images, NIfTIs, the HTML package or participant-level tables.
Only the normal aggregate `logs/records/` run record is intended for Git.

Only a fixed allowlist of acquisition parameters is copied from BIDS JSON.
No patient names, dates, UIDs or private DICOM tags are extracted. Original BIDS
images are still research images: the private storage rule applies even though
new sampled-image headers are constructed without copying source header text.

## What is measured

The exact canonical target mask is verified against `qc/provenance.json`.
Canonical coverage is recomputed from the current fMRIPrep mask. A disagreement
greater than 0.01 percentage points stops that run rather than silently using
stale QC. The additional fixed-reference calculation resamples the run mask
onto the full target grid, retaining the target denominator. Its companion
`mask_grid_contains_target_pct` reveals reference tissue outside the output grid
that could be hidden by resampling a target onto a cropped run grid.

MNI overlays use the same fixed world-coordinate slices for every run:
yellow target contours, cyan fMRIPrep contours and red target-outside-mask voxels.
An additional `missing_focus.png` centers each axis on that run's peak number of
missing target voxels, so small defects between overview planes are not overlooked.
Those focused planes are individualized, not matched between cases and controls;
world-coordinate labels are shown. The full missing-target NIfTI is also retained.
Native views use fractional voxel slices and are not cross-subject or MNI aligned.
Intensity scales are independent between images. Original BIDS echo-2 and MNI
BOLD views average volumes at approximately 25%, 50% and 75% of each series;
this is a static inspection aid, not a temporal artifact assessment.

Native fMRIPrep reference/mask and normalized subject T1w are included when
uniquely available. Ambiguous files are never resolved by taking the first match.
Missing optional evidence is explicitly reported, including aggregate counts.
Missing raw BOLD, MNI BOLD or canonical mask is an inspection failure.

The signal proportions above 1%, 5% and 10% of retained-mask median intensity
are descriptive sensitivity summaries, not validated tissue or dropout tests.
Presence of intensity outside the mask may warrant inspecting mask boundaries;
it can also be interpolation, CSF, noise or nonbrain tissue. **Absence of intensity
in exported preprocessed BOLD is not proof the scanner failed to acquire it**:
masking/resampling can introduce zeros. Original BIDS data are therefore required.

## Human review before any exclusion decision

For each flagged case, compare with the matched controls and inspect:

1. Does original BIDS BOLD show the brain ending at the acquired grid boundary,
   or a consistent missing slab? Check native acquisition geometry and images.
2. Is the acquired field of view sufficient but signal absent locally? Consider
   dropout or distortion; static images alone may not identify the mechanism.
3. Is tissue visible in the original/native image but omitted from the mask?
   Inspect the native reference/mask and MNI mask boundary.
4. Does functional anatomy align with normalized subject T1w and the reference?
   A shift/warp discrepancy warrants fMRIPrep registration-report review. Absence
   of a unique MNI T1w leaves this question unresolved, not automatically passed.
5. Is the mismatch only a reference-versus-subject boundary difference, rather
   than missing acquired brain? Which prespecified task-relevant regions, if any,
   are affected? Separate marginal 98-99% cases from major missing-coverage cases.

Record evidence and uncertainty as acquisition/FOV, dropout, masking,
registration, reference-boundary difference, mixed or indeterminate. These are
review categories, not automatically assigned diagnoses. A package check pass
means the inspection outputs and their lineage passed checks; it does not mean
the scans passed QC, and it does not enact a keep/exclude decision.
