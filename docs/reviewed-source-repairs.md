# Reviewed 10964 And 11935 Repairs

For the subsequent 11935-only masking/source installation and downstream
rebuild, use the [production repair runbook](11935-production-repair.md).
The original two-subject runner below remains staging-only and unpatched;
its historical outputs are not a substitute for that corrected two-run build.

## Decisions And Scope

- 11935 ses-01: PI-approved Faces/Social Doors series 25/26 with magnitude
  reference 23; Doors series 29/30 with magnitude reference 27. The
  [same-month peer report](../logs/records/11935-counterbalance-peers-20261022-235625.txt)
  confirms Faces 25 / Doors 29 for 11924, 11928 and 11929. This corroborates
  Ryan's reconstruction, rather than establishing an independently logged
  stimulus identity for 11935. No further lab question is pending.
- 10964 ses-02: approved newer Faces/Doors sources are mislabeled ses-01.
  `reviewed_behavior_sources.py` maps only their reviewed hashes to ses-02,
  checks the older baseline hashes and timing records, and refuses additional
  correctly named candidates. Original files are never renamed or edited.
  The baseline converter still selects the older historical event fingerprints.
- This is source repair, not QC-based selection. All settled exclusions,
  including 11935's paper exclusion, remain unchanged. Do not rebuild or replace
  Jacob's frozen coverage95 handoff as part of this operation.

## Why Build In Isolation

The running cohort TEDANA comparison freezes production image/confound inputs.
Replacing 11935 now would invalidate that comparison and potentially modify files
being read by active workers. Each repair therefore receives an independent
project under ignored `work/`, copied pipeline code, a private scratch tree,
and separate BIDS/derivatives. Complete FreeSurfer anatomy is copied (not linked)
when available. 10964 baseline anatomy is copied for ses-02 preprocessing;
baseline functional data and existing production derivatives are untouched.
Only Git-tracked files under `code/` are hashed and copied; incidental logs,
caches and other untracked files are not pipeline inputs. Missing or unreadable
tracked files still stop the repair. Code readability is also checked by `plan`.

Lab permissions: the runner explicitly sets `umask 0000`, inherited by its
children. Launch shells must also set `umask 0000` before log redirection. New
isolated copies use shared file/directory modes without importing source ACLs or
restrictive modes; no original permissions are changed. Existing parent-directory
permissions, ACLs, ownership restrictions and read-only mounts can still deny
access. Inspect the private traceback before attempting any permission repair;
do not recursively chmod production or source data.

No promotion command is provided. Passing this runner certifies staged repair
products through confounds, NOT production installation, L1/L2, QC/handoff
refresh, or a scientific inclusion decision. After inspecting the passing logs,
promotion requires an explicit archival/install plan and coordination with the
frozen benchmark. Even when its workers stop, changing inputs invalidates future
checks of that old manifest. Preserve/version its original inputs or retire that
manifest explicitly; do not simply replace files and resume it. Its original
11935 task labels must not be interpreted as repaired data in scientific summaries.

## Checks And Resumption

`plan` verifies behavioral source contracts and, for 10964, writes a private
timestamp-linkage report. Full XA60 acquisitions are identified in the reviewed
export by 872 Faces/Doors or 960 UGR DICOMs, excluding phase/SBRef series.
The four completed behavioral triggers must match one chronological acquisition
assignment with a consistent local scanner/computer clock offset (spread <=5 s).
All started records are preserved in the report, including the earlier Doors
attempt. An unsupported export layout or nonunique timing match stops before
conversion; inspect the private report instead of relaxing the match silently.
This checks timing consistency, not patient identity from DICOM labels.

`build` converts with the dedicated 11935 heuristic or reviewed 10964 source
mapping, verifies all repaired magnitude/phase echoes, source series, lengths,
and SBRefs, then checks events, WarpKit, IntendedFor, MRIQC, fMRIPrep, geometry,
production TEDANA, and confounds. It does not select a new cohort PCA method.
Stages run sequentially: fMRIPrep defaults to 8 CPUs / 32 GB advertised memory,
MRIQC 4 CPUs / 16 GB, WarpKit two jobs, TEDANA one job. These software settings
are not a kernel-enforced memory guarantee; check RAM alongside the benchmark.

Reusing the same private directory preserves checked stages. Existing complete
TEDANA outputs are skipped; partial TEDANA outputs stop for inspection, never
overwritten. Changed code, original protected inputs, or previously validated
products fail closed. Use a new isolated directory for an intentional code
revision; do not edit the receipt or bypass checks. `check` reruns validators.
The runner lock is inherited by children and prevents overlapping work in the
same repair workspace. Exact timing evidence stays in ignored work, while the
compact run record can be shared normally.

## Linux2 Commands

### October 24 Recovery

The v2 10964 attempt converted the wave-2 DICOMs, but failed because its isolated
project lacked the baseline HeuDiConv demographics inventory. The temporary
conversion stage was removed by prepdata's cleanup; no downstream imaging stage
completed. The fix validates the baseline age/sex against the canonical table
before conversion, copies the baseline inventory unchanged, and protects its
hash. It does not substitute wave-2 age or alter original behavior files.

The separate 11935 affine/rigid experiment completed both full fMRIPrep runs.
Only its validation failed on an unnecessary spreadsheet dependency. Coverage
validation now imports only its imaging dependencies. `--validate-existing`
reads saved products read-only and writes a new report, without rerunning
fMRIPrep or the paired reference tests.

Use v3 for 10964 because v2 pins the earlier code. Preserve both older workspaces.
The targeted 11935 source repair uses the newer dedicated runner, not the generic
two-subject loop. Its corrected Faces/Doors acquisitions are distinct from the
historically labeled experiment; saved experimental outputs are not transplanted.

Run these preflights, then the sequential background job below. Nothing here
stops cohort TEDANA, promotes repaired data, changes exclusions, or refreshes QC.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
git pull --ff-only
export AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
export REPAIR_10964="$PWD/work/reviewed-source-repairs-v3"
export SAVED_11935="$PWD/work/11935-init-test-20261023-001417"
export VALIDATION_11935="$PWD/work/11935-validation-$(date +%Y%m%d-%H%M%S)"
export REPAIR_DIR="$PWD/work/11935-final-repair-v1"
"$AUDIT_PYTHON" -c 'import pydicom, nibabel; print("Repair dependencies available")'
"$AUDIT_PYTHON" code/run_reviewed_source_repairs.py plan \
  --subject 10964 --private-dir "$REPAIR_10964"
"$AUDIT_PYTHON" code/run_11935_initialization.py --project "$PWD" \
  --validate-existing "$SAVED_11935" --output "$VALIDATION_11935" --dry-run
"$AUDIT_PYTHON" code/complete_11935_repair.py plan --work-dir "$REPAIR_DIR"
```

Proceed only after all three plans pass. Validate saved 11935 outputs, build
10964, then stage the corrected 11935 acquisitions sequentially. Completed
stages in a compatible existing targeted workspace are preserved.

```bash
STAMP=reviewed-source-repairs-$(date +%Y%m%d-%H%M%S)
umask 0000
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- bash -euc '
    umask 0000
    "$AUDIT_PYTHON" code/run_11935_initialization.py --project "$PWD" \
      --validate-existing "$SAVED_11935" --output "$VALIDATION_11935"
    "$AUDIT_PYTHON" code/run_reviewed_source_repairs.py build \
      --subject 10964 --private-dir "$REPAIR_10964" --jobs 8
    "$AUDIT_PYTHON" code/run_reviewed_source_repairs.py check \
      --subject 10964 --private-dir "$REPAIR_10964"
    bash code/run_11935_completion.sh stage
  ' > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "STAMP=$STAMP"
sleep 5
tail -30 "logs/runs/${STAMP}.nohup.out"
```

Expect saved-run validation, both staged-repair checks, and command exit 0.
Share the run record before any production installation. Do not run `promote`,
`finish`, or `variants` as part of this recovery. Saved validation deliberately
refuses to overwrite a report directory; a repeated validation needs a fresh
`VALIDATION_11935` path. Original experiment outputs remain untouched.

### Permission Failure Before Conversion

The October 23 preflight passed, including a unique 10964 four-run timestamp
match (Doors 9, Faces 13, UGR 17/22). The private traceback subsequently identified
the failure: the old recursive code hash tried to read untracked `code/nohup.out`.
It was not a failure to write imaging outputs or a demonstrated umask problem.
The operator removed that incidental file. The corrected snapshot uses only
tracked code, so another local log cannot cause the same failure.

That attempt created `sub-10964-project/` before hashing, but never wrote its
receipt or copied data. Preserve the v1 workspace for inspection and use the
fresh v2 path at that time. The October 24 recovery above uses v3. Initialization checks code and
protected inputs before creating the project directory. No imaging work was
completed by this failed attempt, so this restart discards no completed stages.
