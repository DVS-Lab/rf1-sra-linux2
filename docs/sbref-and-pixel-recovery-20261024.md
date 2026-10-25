# SBRef and sampled-pixel recovery

## Diagnosed failures

The 11935 functional log and derivative Sources agree: both tasks selected the
Doors echo-1 SBRef. Each retained its task-specific fieldmap. The isolated runner's
SBRef filter listed both tasks. fMRIPrep 25.2.5 `get_sbrefs` updates the current
BOLD entities with that filter; `_select_ref` then chooses the first reference.
This was a runner configuration bug, not an acquisition-identity problem and not
something to fix by rewriting Sources. The existing source-reference guard
correctly prevented completion/promotion.

Upstream implementation:
https://github.com/nipreps/fmriprep/blob/25.2.5/fmriprep/workflows/bold/fit.py

The corrected filter overrides only the absent SBRef `part` entity and preserves
task/run matching. New runs select both tasks correctly. The existing workspace
uses an explicit, backed-up migration selecting only Social Doors for functional
reprocessing. Existing BIDS, anatomy, FreeSurfer, WarpKit, MRIQC and valid Doors
image/transform outputs are hash-protected. JSON provenance annotation remains
part of final validation. All original fMRIPrep files are copied to a verified
backup, original cache and stage receipts remain, and geometry gets a new report
prefix. A distinct stage receipt tracks the corrected functional processing.
Cached unaffected nodes can be reused. Social Doors outputs dependent on the
wrong reference cannot be certified without recomputation. TEDANA/confounds
start only after the corrected source-reference checks pass. Production,
10964, cohort TEDANA, settled exclusions and paper handoff remain unchanged.

All 19 sampled-pixel errors occurred before pixel comparison, at affine
reindexing. NiBabel's enhanced-MR wrapper estimates spacing from two adjacent
positions; rounded positions produced 0.001009-0.007313 voxel residuals over the
full stack. Deriving the slice vector from the first/last positions, after
verifying uniformity of every slice position, reduces the maximum residual in
the supplied 19 header pairs to 0.00004360 voxel. No pixels are interpolated,
geometry is not fitted to BIDS, and the original 0.001-voxel geometry and
0.0001-intensity matching tolerances remain unchanged. Actual pixel comparison
must still run on Linux2. Nonuniform stacks are rejected.

`--retry-report` verifies inventory/container and sample ordering, rehashes inputs
for the original 69 PASS results, carries those results forward without decoding
or conversion, and reruns only the 19 unresolved samples in a new directory.
The old report is never overwritten. A PASS remains limited to one sampled
echo-1 volume per run, not every voxel across every acquisition/time point.

## Linux2 workflow

Use a pinned `git archive` of the published fix into `work/`; do not pull into
the frozen production checkout. The extracted `code/resume_sbref_pixel_checks.sh`
has three modes: `preview` (read-only), `repair` (backup/targeted resume/check), and
`pixels` (new retry report). It defines its own paths and Python environment and
sets umask 0000. Run each through `code/run_logged.sh --include-full-log`.

The repair mode is not a zero-computation validator: Social Doors processing
that used the wrong SBRef must be corrected. It does not reprocess valid Doors
or completed anatomy. Hash checks stop if protected outputs change.

### 1. Linux2: install tools and preview

Run this in the Linux2 terminal, not on the Mac. It fetches without changing
the production checkout. The resolved commit is recorded in the tool directory.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git fetch origin
FIX=$(git rev-parse origin/main)
TOOLS=work/sbref-pixel-fix-v1
mkdir -p "$TOOLS"
git archive "$FIX" code | tar -x -C "$TOOLS"
printf '%s\n' "$FIX" > "$TOOLS/bundle-commit.txt"
bash code/run_logged.sh --label "sbref-preview-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- bash "$TOOLS/code/resume_sbref_pixel_checks.sh" preview
)
```

Stop if the preview fails. Do not rerun the extraction while a recovery is active.

### 2. Linux2: launch independent pixel and repair jobs

Only after the preview succeeds, run this second block in the Linux2 terminal.
Both jobs are detached and write separate timestamped logs.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
TOOLS=work/sbref-pixel-fix-v1
test -f "$TOOLS/bundle-commit.txt"
mkdir -p logs/runs
for MODE in pixels repair; do
  STAMP="sbref-${MODE}-$(date +%Y%m%d-%H%M%S)"
  nohup setsid -f -w bash code/run_logged.sh --label "$STAMP" \
    --include-full-log -- bash "$TOOLS/code/resume_sbref_pixel_checks.sh" "$MODE" \
    > "logs/runs/${STAMP}.nohup.out" 2>&1 &
  printf '%s\n' "Log: $PWD/logs/runs/${STAMP}.nohup.out"
done
)
```

Do not launch this block twice. The repair holds a workspace lock, but that is a
safety guard, not a reason to start duplicate jobs.

### 3. Linux2: publish completed run records

After both commands finish, publish the run records, not private reports:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
python3 work/log-upload-tools/code/publish_run_logs.py --project "$PWD"
```

Downloads are separate from publishing logs. When a private archive is requested,
run its explicit `scp ... ~/Downloads/` command in a Mac terminal, not Linux2.
