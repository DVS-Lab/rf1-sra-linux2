# Resume 11935 With Existing FreeSurfer Anatomy

The October 24 inspection report establishes a naming/copy bug. Production has
`derivatives/freesurfer/sub-11935_ses-01`, with the completion marker, brain and
segmentation volumes, and bilateral white/pial/registered-sphere surfaces.
The final isolated project has neither this directory nor `sub-11935`. The
initializer copied only the latter name and the completion runner required it.
The successful paired experiments already supported the session-qualified name.

This fix preserves the real source basename. It copies existing anatomy into
the isolated project as independent files, verifies SHA256 hashes, and resumes
partial copies without overwriting verified files. Regular-file symlinks are
dereferenced into independent copies; directory/broken symlinks, conflicting
subject directories, changed sources/copies, and active FreeSurfer markers stop
the operation. No production anatomy is renamed, linked, or modified.

The upgrade changes only the geometry-fixed completion runner and its frozen
receipt, backing up the previous bytes. Other frozen code, protected production
inputs, completed products and stage markers are checked and preserved. The
original geometry-only upgrade remains reproducible using its hash-verified
historical payload. Do not edit receipt hashes manually.

## Linux2

Use the published fix commit below. Fetch/archive does not change the production
checkout. Run once with no other 11935 repair active; the helper obtains both
repair locks and stops if occupied. Keep `umask 0000`.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git fetch origin
FIX_REF=REPLACE_WITH_PUBLISHED_FIX_COMMIT
TOOLS="$PWD/work/11935-freesurfer-tools-$FIX_REF"
mkdir -p "$TOOLS" logs/runs
git archive "$FIX_REF" code | tar -x -C "$TOOLS"
export AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
export REPAIR_11935="$PWD/work/11935-final-repair-v1"
STAMP=11935-freesurfer-resume-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 bash "$TOOLS/code/resume_11935_freesurfer.sh" \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "STAMP=$STAMP"
sleep 5
tail -30 "logs/runs/${STAMP}.nohup.out"
)
```

Expected: `FREESURFER VERIFIED: sub-11935_ses-01`, followed by remaining
two-task functional processing and validation. Existing conversion, WarpKit,
MRIQC and any later completed stages are reused. The anatomy copy is I/O,
not `recon-all`; fMRIPrep still uses `--fs-no-resume` and precomputed anatomy.
10964, the paired initialization experiments, cohort TEDANA, production inputs,
paper handoffs and settled exclusions are untouched.

The last report stopped before final functional fMRIPrep, so completing those
two corrected acquisitions can still take time. Success requires both the
final build and check to pass; it does not install products into production.
Review corrected-run images before the separate promotion and downstream
refresh. Do not claim completion from this naming fix alone.
