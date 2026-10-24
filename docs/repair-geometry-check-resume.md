# Resume the reviewed repairs without replacing frozen audits

The October 24 log confirms that 10964 completed preprocessing, production
TEDANA and confounds. The subsequent `check` failed solely because it attempted
to create `repaired.json` and `repaired.tsv` again. This is an orchestration bug,
not evidence of failed image geometry. The same call pattern existed in the
11935 completion runner and is fixed there too.

The fixed runners reuse an existing complete JSON/TSV pair, check that it belongs
to the current isolated workspace, and always run geometry `verify`. Missing,
malformed, mismatched, or incomplete evidence fails closed. The existing geometry
verifier checks current inventory, geometry, transform metadata and applicable
repair provenance. It does not blindly trust an old success marker.

## Frozen-code upgrade

Do not pull into the production checkout, delete geometry reports, erase stage
markers, reset receipts, or create a new 10964 workspace.

`upgrade_repair_geometry_check.py` accepts only the exact reviewed old/new hashes
of two orchestration files. It checks all other frozen code, the production code
inventory and protected production inputs; obtains both repair locks; backs up
the old receipt/code; and records the separate production and staged code hashes.
It preserves imaging files, stage markers, reports and completed processing.
An interrupted file replacement can be resumed from its journal. Unexpected
code changes or an active repair cause a stop. The cohort experiment is neither
locked nor modified. All commands retain `umask 0000`.

### Older 11935 staging workspace

The `20261023-081711_11935-final-stage` log records initialization at `ca4323cd`,
before 10964's newer snapshot. It completed conversion, WarpKit and MRIQC, then
stopped because the complete FreeSurfer copy was unavailable. Later logs must
establish which additional stages finished; the October 24 failure does not
mean those earlier products were lost.

The first upgrade helper incorrectly required this older 11935 code inventory
to equal the newer production checkout. The helper now recognizes only the
exact `ca4323cd` to `591d29d7` differences: the reviewed runner's 10964-only
baseline safeguards and `run_11935_initialization.py`'s main-entry umask setting.
The original initialization module stays frozen. All other code, protected
inputs and stage markers are still checked. Unrecognized differences stop with
the affected filenames. Do not replace the receipt with current hashes manually.

After 10964 passes, run only `finish-11935` using the newly published helper;
there is no need to repeat 10964. The two-task build may still stop on a genuine
missing FreeSurfer prerequisite; it will not silently rerun anatomy.

## Linux2 launch

After the fix has been published, use its exact commit in `FIX_REF` below. Fetch
does not change tracked files used by frozen repairs or cohort TEDANA.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git fetch origin
FIX_REF=REPLACE_WITH_PUBLISHED_FIX_COMMIT
TOOLS="$PWD/work/geometry-check-tools-${FIX_REF}"
mkdir -p "$TOOLS" logs/runs
git archive "$FIX_REF" code | tar -x -C "$TOOLS"
export AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
export REPAIR_10964="$PWD/work/reviewed-source-repairs-v3"
export REPAIR_11935="$PWD/work/11935-final-repair-v1"
STAMP=reviewed-geometry-resume-$(date +%Y%m%d-%H%M%S)
export TOOLS
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  bash -euc '
    umask 0000
    bash "$TOOLS/code/resume_reviewed_geometry_checks.sh" check-10964
    bash "$TOOLS/code/resume_reviewed_geometry_checks.sh" finish-11935
  ' > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "STAMP=$STAMP"
sleep 5
tail -30 "logs/runs/${STAMP}.nohup.out"
)
```

10964 runs checks only. For 11935, the October 24 log validated/exported the
saved affine and rigid experiments but stopped before final two-task staging.
Those experiments are not rerun. If final staging exists, its completed stages
are preserved and checked; if it has never started, the two corrected task runs
still require the planned staging pipeline. This can take time and is not a
repeat of the completed initialization experiments. A ready staged result is
checked without invoking build.

Success is separate for each subject. Production installation, visual acceptance
of 11935, and downstream refresh remain separate reviewed actions. Settled
exclusions and the paper handoff are unchanged.
