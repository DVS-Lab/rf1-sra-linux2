# Shared Reward source-validity follow-up, 2026-09-15

Scope: hand downstream analysis valid images/events and documented stimulus
identity. **Do not make imaging-QC exclusions here.** Cooper owns motion, tSNR,
coverage, ratings/covariate adjudication and the eventual analysis sample.
This note narrows the Shared Reward items in
[historical-tracker-reconciliation.md](historical-tracker-reconciliation.md).
Historical working workbooks are evidence, not an executable exclusion list.

## 10657: run-scoped, conditional PI agreement

Ryan's supplied reply reports that the session notes identify **Shared Reward
run 1 only** as incorrectly collected because the friend name was wrong. The
historical workbook says the photograph was correct. The task code at the
original scan commit (`098d768e3` in private `rf1-sra`) confirms that the entered
friend name is drawn alongside the photo during the decision period. The raw
CSVs do not save the entered name or a hash of the displayed `friend.png`.

The PI agrees with excluding Shared Reward run 1 and retaining run 2 **assuming
the name was corrected for run 2**. Record that as conditional agreement, not
proof of the correction. Confirm run-2 correction from session/operator evidence
before final source-validity sign-off. No new blanket subject exclusion, no
contrast-specific salvage, and no Trust change are authorized by this evidence.
Ryan's suggestion about the preceding Trust runs is explicitly a suspicion.
The separate accepted smoothing-tolerance exception for run 1 is unrelated.

This pass records the decision but does not change generated manifests or the
downstream curated exclusion table while that conditional scope is unresolved.

## 10668: count raw acquisition episodes before assigning attempts

Private scan commit `8c3b66ea6` contains a single Shared Reward CSV with two
54-trial segments. Both match the scheduled **run-1** design. Commit `3f530e1e8`
later split first/second segments into raw run-1/run-2 filenames, preserving a
`run-1_raw.csv~` copy. The current converter's filename mapping selects the
first segment for BIDS Shared Reward run 1. Current BIDS/QC inventories show
one Shared Reward BOLD run, not two. Filename labeling does not prove the match.

The PI's intended chronological mapping is appropriate **if two corresponding
acquisition episodes are established**: first attempt to first episode, second
attempt to second episode. Check raw DICOMs, including the neighboring Trust
series, rather than trusting BIDS labels. One or three episodes, an aborted
acquisition, a rerun, a task running on the wrong computer, or a missing BIDS
conversion requires explicit reconstruction; do not silently discard an attempt
or renumber sources. Multi-echo magnitude, phase, repeated copies and SBRefs
must not inflate the acquisition count. Conversely, do not hide a genuine
repeat by merging equal protocol names or series numbers across studies.

Ryan reports that Shared Reward run 1 followed the error. His proposed detailed
sequence is interpretation, not a confirmed mapping. The CSVs have relative
timing, not absolute task timestamps. Same design, plausible duration or better
behavior cannot select the correct attempt. The raw timeline may narrow the
mapping; if synchronization evidence is absent, request that precise fact only.

## 11913/11923: source identity, not a presumed task failure

The operational tracker reports late `11923` scans registered as `11913`, but
does not identify which tasks were affected. Compare both source-folder trees,
study/series identities, patient-registration consistency, acquisition dates,
series order and behavioral visit context. Do not change BIDS identities or
exclude either subject on the tracker alone.

**Important:** `prepdata.sh` calls `shiftdates.py`, which subtracts 1,200 months
from BIDS `scans.tsv` dates. Do not compare those dates directly with raw DICOM
dates as if they were both unmodified. Scanner/task-computer clocks also need
not agree without documented synchronization.

## Read-only collection on Linux2

`code/audit_sharedreward_sources.py` reads all DICOM headers (no pixels) under
top-level source directories whose names match the three exact subject IDs.
It groups by study + series UID, deduplicates SOP instances, retains echo/part
information and repeated-series evidence, inventories current BIDS Shared
Reward echo-1 magnitude runs, and fingerprints the 10668 behavioral segments.
It does **not** infer an acquisition count from raw series count or decide
which attempt belongs to a scan. It includes all named matching visit folders;
the BIDS comparison is explicitly session 01. Sources outside those matching
folders cannot be ruled out by this scoped inventory.

Use the existing HeuDiConv container's Python (`pydicom` and `nibabel`) so no
Conda activation or package installation is needed:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only origin main
git -C /ZPOOL/data/projects/rf1-sra pull --ff-only origin main

audit_tag="sharedreward-source-validity-$(date +%Y%m%d-%H%M%S)"
mkdir -p logs

nohup bash code/run_logged.sh \
  --label "$audit_tag" --include-full-log -- \
  apptainer exec --cleanenv \
    --bind "$PWD:/project" \
    --bind /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/source:ro \
    --bind /ZPOOL/data/projects/rf1-sra/stimuli:/behavior:ro \
    /ZPOOL/data/tools/heudiconv-1.4.0.sif \
    python /project/code/audit_sharedreward_sources.py \
      --source-root /source \
      --bids-root /project/bids \
      --behavior-root /behavior \
      --private-output "/project/work/$audit_tag" \
  > "logs/$audit_tag.nohup" 2>&1 < /dev/null &

printf 'Audit PID: %s\nLog: logs/%s.nohup\n' "$!" "$audit_tag"
```

Exact DICOM dates/UIDs/registration IDs and full BIDS sidecars stay under the
new ignored `work/` directory (0700; output files 0600). Do not upload that JSON
or force-add it. The tracked run record contains only redacted tokens,
relative timing, whitelisted task hints, counts and behavioral fingerprints.
Tokens are comparable only within one audit. Header failures/missing input
groups cause a nonzero exit; header warnings are counted for review.
`CHECK PASSED` means **inventory collected**, not mapping/eligibility approved.

Review the completed redacted run record before committing it. If exact source
inspection is subsequently needed, keep it private and publish only the scoped
conclusion/evidence, reviewer and date. Do not rerun preprocessing or FEAT until
the affected source mapping and downstream rebuild scope are established.
