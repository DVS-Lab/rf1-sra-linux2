# Shared Reward source-validity follow-up, 2026-09-15

Scope: hand downstream analysis valid images/events and documented stimulus
identity. **Do not make imaging-QC exclusions here.** Cooper owns motion, tSNR,
coverage, ratings/covariate adjudication and the eventual analysis sample.
This note narrows the Shared Reward items in
[historical-tracker-reconciliation.md](historical-tracker-reconciliation.md).
Historical working workbooks are evidence, not an executable exclusion list.

## Active handoff scope, 2026-09-29

The three Shared Reward source-validity decisions are settled: `10657` run
disposition, the PI-approved `10668` reconstruction, and the recorded source
links for `11913`/`11923`. Implementation and Linux2 verification of the first
two remain pending; they are no longer requests for repeated lab review.
Demographics/preflight is complete and GitHub issue #1 is closed.
The separate Trust, Doors and UGR recovery/validity backlogs retain their
existing Linux2 status; they are not part of this team request. Do not request
another lab review of them through the Shared Reward handoff. Data quality,
including mask coverage, is a later task-level stage.

For `10657`, **exclude Shared Reward run 1 and retain run 2**. Ryan supplied the
session form marking run 1 as having a deviation and run 2 as having no task
deviations; the PI accepted this evidence. This is not a direct saved record of
the corrected name. Do not reopen photograph identity or infer a Trust exclusion.

For `10668`, the [presented-task reconstruction](10668-task-reconstruction.md)
uses the existing inventory and original appended-log history. The likely
sequence is Trust, Shared Reward attempt A during the Trust-run-2-labeled scan,
then Shared Reward attempt B during the SharedReward-labeled scan. Ryan supported
relabeling the second Trust scan as Shared Reward, and the PI accepted the
reconstruction and first-255-volume trim. Record this as a reviewed interpretation,
not timestamp-proven display/trigger identity. Scanner labels do not establish
presented task. The historical blanket Trust-plus-Shared-Reward exclusion is not
the current decision. The exact repair contract is in the reconstruction note.

For `11913`/`11923`, the September 29 01:11 conversion-provenance check has now
completed the recorded source-series linkage (see below). No cross-folder
Shared Reward assignment or conflicting metadata was found. No new lab request,
identity repair, or Shared Reward exclusion is indicated by this evidence.
The exact referent of the historical registration note remains unproven; do
not turn that limitation into another broad lab question or claim that scanner
registration was independently verified against the participant.

**Collection completed 2026-09-16:** the
[run record](../logs/records/20260916-000438_sharedreward-source-validity-20260916-000438.md)
contains the redacted inventory. See the [September 27 closeout](audit-status-20260927.md)
for its interpretation and remaining actions. The collection commands below
are retained for reproducibility, not a request to repeat the completed run.

## 10657: reviewed run disposition; implementation pending

Ryan's supplied reply reports that the session notes identify **Shared Reward
run 1 only** as incorrectly collected because the friend name was wrong. The
historical workbook says the photograph was correct. The task code at the
original scan commit (`098d768e3` in private `rf1-sra`) confirms that the entered
friend name is drawn alongside the photo during the decision period. The raw
CSVs do not save the entered name or a hash of the displayed `friend.png`.

The earlier conditional agreement is superseded by Ryan's session-form evidence
and the PI's acceptance: exclude Shared Reward run 1; retain run 2. The form
explicitly records no task deviations for run 2. Preserve that basis rather
than claiming an explicit name-change log exists. No blanket subject exclusion, no
contrast-specific salvage, and no Trust change are authorized by this evidence.
Ryan's suggestion about the preceding Trust runs is explicitly a suspicion.
The separate accepted smoothing-tolerance exception for run 1 is unrelated.

This pass records the final decision but does not change generated manifests or
the downstream curated exclusion table. Propagate the run-1-only disposition
and verify that run 2 remains eligible before declaring implementation complete.

## 10668: PI-approved reconstruction; implementation pending

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

The inventory establishes one **SharedReward-labeled** acquisition, not that
Shared Reward was presented in only one acquisition. The September 29
conversion records link canonical Shared Reward run 1 to magnitude series 14.
The [approved reconstruction](10668-task-reconstruction.md) pairs series 11
(Trust run 2 label) with attempt A and series 14 with attempt B.
This uses three existing episodes, not extra phase/echo/SBRef acquisitions.
Original append order supports A before B. The PI accepted residual historical
display/trigger uncertainty after Ryan's clarification; do not present that
uncertainty as an outstanding lab request. The existing series-14/A event pairing
needs correction as well as recovery of the other Shared Reward episode.
No reassignment has been applied yet.

Ryan's follow-up still interprets the ambiguous phrase about rerunning Trust,
but explicitly supports relabeling the second Trust scan as Shared Reward run 1.
The PI approved proceeding on the combined notes, acquisition chronology and
original behavioral append order. The CSVs have relative timing, not absolute
task timestamps; neither duration nor behavioral quality alone selects a source.
Both attempts passed actual FSL task-only design tests at 255 and 280 volumes
(10/10 task rank, 22/22 retained activation contrasts estimable). This does not
certify the full nuisance GLM or require trimming; see the reconstruction for
the exit-screen tail and remaining acquisition-parameter comparison.

## 11913/11923: source identity, not a presumed task failure

The operational tracker reports late `11923` scans registered as `11913`, but
does not identify which tasks were affected. The collected source inventory and
saved conversion records have now been compared; do not change BIDS identities
or exclude either subject on the tracker alone.

### Verified conversion links, 2026-09-29

The [01:11 Linux2 review](../logs/records/20260929-011103_sharedreward-conversion-links-20260929-011103.md)
exited 0 with **5/5 PROVENANCE_UID_LINKED** and no conflicting metadata:

| Canonical Shared Reward run | Recorded source folder | Magnitude series |
| --- | --- | --- |
| `10668` run 1 | `10668` | 14 |
| `11913` run 1 | `11913` | 25 |
| `11913` run 2 | `11913` | 29 |
| `11923` run 1 | `11923` | 25 |
| `11923` run 2 | `11923` | 33 |

The two series numbered 25 are distinct UID-backed records, not one ambiguous
source reused between participants. The check used unchanged live sidecars,
effective saved edit-table assignments, sequence UIDs and populated filegroups;
all three conversion-record hashes per subject are in the receipt. Inventory
SHA-256: `f4cd81016314c9cef0df705ed3f875741e02678f2f59cebb939d96b4bc42fac0`.

This completes the recorded Shared Reward source-link engineering step. The
September 16 chronology places the late repeated `11923` acquisitions in
Trust run 2, not Shared Reward. That is consistent with a narrower scope for
the old note, but does not establish precisely which scans the note described
or whether registration was corrected before export. Record this limitation;
do not assert that the historical note was disproved or proven to concern Trust.
No Shared Reward swap/correction is supported by the inspected records, and no
new lab escalation is warranted solely by the former series-number ambiguity.

These are recorded conversion links, not a pixel-wise reconversion comparison
or independent participant-registration proof. No data or eligibility was
changed by that check. Subsequent human review settled the `10657` disposition
and `10668` reconstruction described above; only implementation and verification
remain for this handoff.

**Important:** `prepdata.sh` calls `shiftdates.py`, which subtracts 1,200 months
from BIDS `scans.tsv` dates. Do not compare those dates directly with raw DICOM
dates as if they were both unmodified. Scanner/task-computer clocks also need
not agree without documented synchronization.

## Review the existing inventory on Linux2

**Completed successfully at 01:11 on September 29.** Commands below are retained
for reproducibility, not a request to run the same check again.

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

Keep the affected runs visibly pending repair/verification when preparing
downstream work; successful rendering must not silently substitute for the
approved remapping or run-1 exclusion. The human decisions are settled, but
their implementation is not. Unrelated technically valid inputs can proceed.

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
