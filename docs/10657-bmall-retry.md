# 10657 all-volume smoothing diagnostic

The completed 6-mm evaluation has five slightly below-band outputs for 10657,
ses-01: Doors run 1, Social Doors run 1, Shared Reward run 1, Trust runs 1 and 2.
This is a processing-target diagnostic, not a scientific exclusion decision.
Shared Reward run 1 remains excluded and run 2 retained. No Trust exclusion or
participant-wide exclusion is inferred. Nothing is promoted to task analyses.

## Output locations

- Original cohort outputs: `derivatives/smoothness-evaluation-6mm-v1/runs/`.
- New retry: `derivatives/smoothness-10657-bmall-v1/runs/<run-label>/`.
- New filenames end in `_desc-smoothToFWHM6Bmall_bold.nii.gz`.
- Diagnostics, comparison TSV, validation JSON, failed attempts and controller
  logs live under the new retry root. These are not the production Shared Reward
  analysis layout and do not replace existing smoothing products.

The retry uses original unsmoothed fMRIPrep images, original masks and the same
AFNI executable identities. The controller changes only by using `-bmall` and
omitting `-quiet` to retain stopping diagnostics. The independent measurement
uses the unchanged, frozen Shared Reward `measure_smoothness.sh`. We record
directional classic FWHM, combined FWHM, ACF parameters, mask voxel counts,
image dimensions and voxel sizes. The original logs may not contain stopping
details because their controller used `-quiet`.

Both original experiment locks and the retry lock must be available. Locks are
inherited by subprocesses. Never delete lock files or bypass a lineage failure.
The original five result hashes, input hashes and QC table hash are checked;
existing evaluation code is unmodified. Failed attempts stay available, and a
valid completed retry is verified, not recomputed (even if still outside band).
Only the new retry directory receives results. No participant-level data are
automatically staged for Git.

## Linux2 launch

Run after this helper is published. There are only five runs, processed serially
with one AFNI thread, avoiding any interaction with other work on the machine.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
export PATH="/ZPOOL/data/tools/anaconda/tug87422/envs/sharedreward-phase0/afni-bin:$PATH"
export AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
STAMP=smoothness-10657-bmall-$(date +%Y%m%d-%H%M%S)
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/retry_10657_bmall.py run \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "STAMP=$STAMP"
sleep 5
tail -30 "logs/runs/${STAMP}.nohup.out"
)
```

No `plan`, overwrite, QC refresh, cohort restart, or production installation is
needed. Same command resumes only unfinished retry entries. Exit 0 means all
five validated within the existing 5.4-6.6-mm band; exit 2 means technically
complete with target-review items; exit 1 means a processing/integrity problem.
The 6-mm band applies to classic combined FWHM, not to ACF effective FWHM.

## Verify and publish after completion

This independent check never runs smoothing. It records all comparison metrics
and original/retry log tails in a publishable run record.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
if pgrep -u "$USER" -af '[p]ython.*code/retry_10657_bmall.py run'; then
  echo "STOP: retry still running; wait before validation."
  exit 1
fi
export PATH="/ZPOOL/data/tools/anaconda/tug87422/envs/sharedreward-phase0/afni-bin:$PATH"
PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
status=0
bash code/run_logged.sh \
  --label "smoothness-10657-bmall-check-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- \
  env PYTHONUNBUFFERED=1 "$PYTHON" code/retry_10657_bmall.py check || status=$?
echo "Diagnostic check exit: $status (0=within band; 2=target review; 1=error)"
python3 code/publish_run_logs.py --project "$PWD"
exit "$status"
)
```

Review the five paired results before adopting any retry. A target mismatch is
not an eligibility decision, and an improvement cannot reinstate an already
excluded run. This does not address the separate XA60 ACF difference.

## Tests and limits

Tests use synthetic NIfTI images, the existing frozen-evaluation fixtures and
mocked AFNI execution; they test preservation, selection, failure/resume,
lineage, locks and review status, not numerical AFNI behavior. The Linux2 run
is the real numerical test. AFNI documents that `-bmall` uses every blurmaster
volume instead of its default subset; its effect here is a hypothesis, not a
diagnosed cause: https://afni.nimh.nih.gov/pub/dist/doc/program_help/3dBlurToFWHM.html
