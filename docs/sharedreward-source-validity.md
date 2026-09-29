# Shared Reward source-validity follow-up, 2026-09-15

Scope: hand downstream analysis valid images/events and documented stimulus
identity. **Do not make imaging-QC exclusions here.** Cooper owns motion, tSNR,
coverage, ratings/covariate adjudication and the eventual analysis sample.
This note narrows the Shared Reward items in
[historical-tracker-reconciliation.md](historical-tracker-reconciliation.md).
Historical working workbooks are evidence, not an executable exclusion list.

## Active handoff scope, 2026-09-29

This Shared Reward cleanup has exactly three items: `10657` run-2 name
correction, `10668` behavioral-attempt synchronization, and the engineering
source-link closeout for `11913`/`11923`. Demographics/preflight is complete.
The separate Trust, Doors and UGR recovery/validity backlogs retain their
existing Linux2 status; they are not part of this team request. Do not request
another lab review of them through the Shared Reward handoff. Data quality,
including mask coverage, is a later task-level stage.

The only immediate human question is: **For 10657, was the displayed friend
name corrected before Shared Reward run 2?** Run 1's displayed-name error and
the agreed exclusion are established. Retain run 2 conditional on that answer;
do not reopen photograph identity or infer a Trust exclusion.

For `10668`, use the existing inventory and source chronology first. If these
cannot identify the synchronized attempt, ask only which of the two attempts
accompanied the one Shared Reward acquisition. The historical blanket
Trust-plus-Shared-Reward exclusion is not the current decision.

For `11913`/`11923`, finish the source-series linkage below on our side before
escalating anything to the team. Neither successful inventory collection nor
unique folder/protocol labels close participant identity by themselves.

**Collection completed 2026-09-16:** the
[run record](../logs/records/20260916-000438_sharedreward-source-validity-20260916-000438.md)
contains the redacted inventory. See the [September 27 closeout](audit-status-20260927.md)
for its interpretation and remaining actions. The collection commands below
are retained for reproducibility, not a request to repeat the completed run.

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

September 29 local history recheck confirmed that `3f530e1e8` introduced the
run-2 filename during the later split, not during the acquisition. It adds no
independent synchronization evidence. The completed September 16 inventory
establishes one Shared Reward acquisition after two Trust-labeled acquisitions.

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

## Review the existing inventory on Linux2

The [September 29 sidecar-only review](../logs/records/20260929-010049_sharedreward-source-links-20260929-010049.md)
completed with exit 1: all five live sidecars were unchanged and the saved
inventory was complete, but no exact UID links were available. The matching
series numbers were 14 for `10668`, 25/29 for `11913`, and 25/33 for `11923`.
Both series-25 entries satisfy the same limited sidecar constraints. This is
an evidence limitation, not evidence that data were swapped or a new processing
failure. It is not a new lab question.

Do not recollect the DICOM headers. The new standard-library-only reviewer
consumes the existing private JSON and checks that the live canonical BIDS
sidecars still match its snapshot. It searches all inventoried source folders,
not only the participant named in each BIDS path. It never chooses a behavioral
attempt or changes data/eligibility. Raw identifiers and timestamps stay private.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only origin main

bash code/run_logged.sh \
  --label "sharedreward-source-links-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- \
  python3 code/review_sharedreward_inventory.py \
    --inventory work/sharedreward-source-validity-20260916-000438/inventory.json \
    --conversion-provenance
```

This is a short metadata-only check; no `nohup` or imaging rerun is needed.
Share only its redacted `logs/records/` record, never the private JSON.
With `--conversion-provenance`, the reviewer follows the saved
`.heudiconv/<subject>/ses-01/info/<subject>_ses-01.edit.txt` output assignment
to `dicominfo_ses-01.tsv`'s `series_uid`, then to the existing raw inventory.
It requires the selected sequence's populated `filegroup_ses-01.json` entry,
checks its count against `series_files` when present, and compares available
sidecar/conversion metadata with the source inventory. All three record hashes
are printed; no raw contents are printed. The saved heuristic is never executed,
and `.auto.txt` is not silently substituted for the effective edit table.
This follows the [HeuDiConv 1.4.0 conversion-table contract](https://github.com/nipy/heudiconv/blob/v1.4.0/heudiconv/convert.py).

Exit 0 means all five Shared Reward echo-1 records have consistent recorded
UID links, not that the three source-validity items are approved or NIfTI pixel
identity has been independently proven. Exit 1 records unresolved links/incomplete evidence, not a
new preprocessing failure. Exit 2 means the review could not run.

Without the new flag, sidecars lacking `SeriesInstanceUID` still produce
candidates, never exact links. With the flag, `PROVENANCE_UID_LINKED` identifies
the recorded conversion chain. Missing/unsupported conversion records remain
unresolved instead of falling back to a candidate. Inspect those records
privately on Linux2; do not ask the lab to redo source review merely because
a UID was omitted from a sidecar. Changed/missing sidecars require engineering
reconciliation with the current conversion before using the snapshot.

The September 16 chronology places the late repeated `11923` acquisitions in
Trust run 2, not Shared Reward. This narrows the historical note's possible
scope; it does not prove which episode the note described or clear an identity
exception. Preserve that distinction in the final source-mapping receipt.

## Technical work independent of the closeouts

Continue code/contract validation and read-only completeness checks without
changing models, preprocessing or QC policy. Local checks on September 29
tested the pooled Shared Reward full-trial contrast definition, FSF rendering,
EV generation and L2 runner separately from source-validity decisions. These
tests do not certify live Linux2 outputs or approve a final analysis cohort.
The current runner's environment-dependent test status is recorded in the
local validation receipt. No scientific decision is inferred from tests.

Keep the affected runs visibly unresolved when preparing downstream work;
successful rendering or processing must not silently mark their sources valid.
Unrelated technically valid inputs do not have to await these three closeouts.

## Original read-only collection on Linux2 (already completed)

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
