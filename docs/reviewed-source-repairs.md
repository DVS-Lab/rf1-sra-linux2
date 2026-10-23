# Reviewed 10964 And 11935 Repairs

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

Run from production root after pulling the repair code. The first command is
preflight only; proceed only if both plans pass:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
export AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
export REPAIR_DIR="$PWD/work/reviewed-source-repairs-v1"
"$AUDIT_PYTHON" -c 'import pydicom, nibabel; print("Repair dependencies available")'
bash code/run_logged.sh --label "reviewed-repair-plan-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- bash -euc '
    for subject in 10964 11935; do
      "$AUDIT_PYTHON" code/run_reviewed_source_repairs.py plan \
        --subject "$subject" --private-dir "$REPAIR_DIR"
    done'
```

Build the two repairs sequentially, not two concurrent fMRIPrep jobs:

```bash
STAMP=reviewed-source-repairs-$(date +%Y%m%d-%H%M%S)
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- bash -euc '
    for subject in 10964 11935; do
      "$AUDIT_PYTHON" code/run_reviewed_source_repairs.py build \
        --subject "$subject" --private-dir "$REPAIR_DIR" --jobs 8
      "$AUDIT_PYTHON" code/run_reviewed_source_repairs.py check \
        --subject "$subject" --private-dir "$REPAIR_DIR"
    done' > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "STAMP=$STAMP"
sleep 5
tail -30 "logs/runs/${STAMP}.nohup.out"
```

Expect two isolated-repair `CHECK PASSED` results and command exit 0. Share the
run record before any production installation. No production file deletion,
manual task rename, source-exclusion change, or benchmark restart is required.
