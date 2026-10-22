# No-TEDANA Unselected Run Reconciliation

## 11935 Mapping Verification

The [22:12 mapping report](../logs/records/11935-task-mapping-20261021-221243.md)
at commit `3fa1b0ff` establishes the following, superseding the mapping hypotheses
below:

- Source descriptions identify series 25/26 and 29/30 as two full-length,
  face-labeled functional pairs (`dim4=872` for each); 26/30 have phase labels.
  Their preceding reference pairs are 23/24 and 27/28, respectively.
- Both saved `.auto.txt` and `.edit.txt` mappings select only magnitude 29 and
  phase 30 for `task-socialdoors`. The Doors mappings are empty. Pair 25/26 was
  omitted from this saved task conversion mapping.
- The live BIDS `task-socialdoors_run-1_echo-1_part-mag_bold.json` reports
  `SeriesNumber=29`. Existing Social Doors therefore uses the second acquisition,
  not the first. This confirms scanner-series lineage, not presented-task identity.
- The saved Social Doors SBRef mapping contains **both 23 and 27** despite one
  selected BOLD pair. This differs from the current heuristic's single-last-SBRef
  assignment and raises a possible cross-acquisition reference pairing. Verify
  actual BIDS SBRef sidecar series numbers and fMRIPrep's selected input before
  claiming a mismatch. A mismatch, if found, would not by itself prove the cause
  of the existing mask defect.
- Current behavioral files contain distinct complete tasks: Doors decision stimuli
  use `SD...jpg` and faces use `MF...jpg`. The raw files contain only onset,
  duration, trial type, RT and response; converted files add stimulus fields.
  No absolute task-start time or scanner-series link is present. Each raw task
  starts near zero and spans approximately 331 seconds. Relative timing, equal
  lengths, file names, Git ordering and scanner labels cannot identify which task
  ran during which acquisition.

### Smallest Remaining Human Fact

For **11935 session 01**, was the first of the two face-labeled acquisitions
(functional series 25/26) the faces task and the second (29/30) Doors, or was
the order reversed? Confirm from acquisition/session notes or an independent
runtime record, including any restart or task/scanner synchronization problem.
If records do not establish this, keep the identity unresolved rather than
choosing the usual order. No broad new source search or Jacob QC review is needed.

### Conditional Repair Plan (Not Authorized Or Applied)

| Confirmed task order | Correct Social Doors source | Correct Doors source |
| --- | --- | --- |
| Faces first, Doors second | 25/26 with its own 23/24 references | 29/30 with its own 27/28 references |
| Doors first, Faces second | 29/30 with its own 27/28 references | 25/26 with its own 23/24 references |

Before conversion, verify the raw series still exist, echo/phase completeness,
actual output dimensions, and acquisition parameters. Use isolated conversion
outputs first. Do not merely rename an existing FEAT directory, copy an image
under both tasks, or reuse affected derivatives against a different event file.
After approved mapping, rebuild affected fieldmaps, references/masks, preprocessing
and no-TEDANA task analyses with verified lineage and matched behavior. Preserve
unaffected runs, source data, and the current coverage95/model decisions; do not
automatically reinstate a run because conversion or coverage improves.

No recovery has been executed. The existing Social Doors task identity is **not
confirmed**, even though its SeriesNumber lineage is. The current paper coverage
exclusion already withholds that run and remains intact.

## Acquisition-Series Closeout

The [22:05 saved-series report](../logs/records/no-tedana-source-series-20261021-220550.md),
received at commit `0dbf5fc1`, covers all 26 subjects in the 47-row queue.
This section supersedes the preliminary partition below. It closes processing
questions within the reviewed dataset, not the possibility of unexported or
mislabeled data elsewhere. No new exclusion policy or file changes are implied.

| Current disposition | Rows | Next action |
| --- | ---: | --- |
| Unavailable in reviewed dataset | 40 | Remove from routine processing-repair queue; retain availability reasons, not QC exclusions. Reopen only on new source evidence. |
| Preserved model exclusion/hold | 3 | 11201 UGR r1; 11125 Social Doors r1 and Doors r1. Unchanged. |
| Known very short, unusable full-task input | 1 | 11203 Doors r1. Unchanged; one behavioral trial. |
| Partial-run salvage candidates | 2 | 10812 and 11203 Social Doors r1. Not approved for the fixed full-run pipeline. |
| Full-length source-label/conversion recovery candidate | 1 | 11935 Doors r1; investigate both Social Doors-labeled acquisitions before relabeling. |
| **Total** | **47** | No new recovered outputs or increase in N yet. |

### Unavailable Slots: 40

- UGR r2 only (12): **10572, 10603, 10617, 10690, 10713, 10881, 11374,
  11439, 11443, 11462, 11679, 11815**. Each saved inventory contains one
  UGR acquisition group, not two, and no canonical second behavioral source
  resolves. Paired magnitude/phase series are not two task runs. Preserve the
  usable first run. The explicit skipped-run notes for 10617/10690/10713 remain
  intact. 10572's older second-run imaging checkbox is not supported by this
  inventory; it does not justify another processing job.
- UGR r1 and r2 (10): **11085, 11125, 11203, 11396, 11692**. No UGR-labeled
  series in the saved baseline inventories and no resolved baseline UGR sources.
- Both Social Doors r1 and Doors r1 (18): **10913, 11075, 11083, 11085,
  11110, 11128, 11145, 11396, 11443**. Neither task appears in the saved baseline
  acquisition inventories; neither baseline behavioral source resolves. The
  11110 tracker checkboxes are not corroborated by the exported-source audit or
  saved inventory. Later session-02 data do not fill baseline slots.

These are run-level availability dispositions for the currently reviewed
dataset, not participant exclusions, new acquisition-failure diagnoses, or
claims that an archive-wide search proved noncollection. In particular, a
protocol label does not prove the actual displayed task when independent
evidence establishes a computer/scanner mismatch.

### Partial Acquisitions: 10812 And 11203

| Subject/task | Saved series | Recorded dim4 | Behavior | Interpretation |
| --- | --- | --- | --- | --- |
| 10812 Social Doors r1 | 17, 18 | 680 each | 40 trials | Shorter than the normal 872; candidate partial acquisition despite a complete behavior log. |
| 11203 Social Doors r1 | 20, 21 | 748 each | 35 trials | Shorter than the normal 872; consistent with the previously documented partial acquisition. |
| 11203 Doors r1 | 23, 24 | 48 each | 1 trial | Very short input, not a full task; unchanged disposition. |

Both RF1 and XA30 heuristics require `dim4 == 872` for these tasks. Thus their
nonselection is explained by the exact-length gate, not by a failed downstream
FEAT job. Under the four-echo interpretation these counts suggest 170, 187,
and 12 volumes respectively, but those are not newly verified NIfTI lengths.
Any salvage must establish echo/phase completeness, image-to-event alignment,
which events were actually imaged, and contrast estimability. Do not pad BOLD,
include post-acquisition events, relax the heuristic globally, or silently
change the paper model. No salvage has been approved or performed.

### 11935: Full-Length Candidate, Not Yet A Validated Repair

The inventory contains two Social Doors-labeled groups: SBRefs 23/24 with
functional series 25/26, followed by SBRefs 27/28 with functional series 29/30.
All four functional series have `dim4=872`. There is no Doors-labeled group,
and there are complete behavioral sources for both tasks.

`heuristics_XA30.py` assigns matching Social Doors series with
`info[srSocial_mag] = [s.series_id]` (and similarly for phase/SBRef), so a later
match replaces an earlier match in the mapping. RF1 has the same single-run
assignment pattern. This is a plausible explanation for one labeled task
surviving conversion while the other appears missing. The current report's
normalized task hints do not establish exact protocol text, magnitude/phase
roles, the historical conversion mapping, or which task the participant saw.

Next: inspect the original protocol/description fields, saved auto/edit
conversion mappings, and live BIDS sidecar series numbers for this subject.
Then establish the task chronology from independent runtime/session evidence.
Do not assume that the second acquisition was Doors just because that order is
plausible. This may affect the identity of the existing Social Doors input as
well as recovery of Doors. Its existing coverage95 exclusion remains unchanged;
the separate mask/registration investigation is not evidence for task identity.

## Preliminary Review (Superseded Where Noted Above)

## Scope And Limits

Reconciled on 2026-10-21 against the complete frozen
[47-row preparation report](../logs/records/no-tedana-unselected-run-review.md)
at Linux2 commit `faac2f94`. All rows below are session 01. This is an evidence
ledger, not a new exclusion list. No source files, manifests, QC thresholds,
FEAT outputs, or eligibility were changed.

The 22 UGR, 12 Social Doors, and 12 Doors `missing_or_invalid` slots plus one
UGR hold are not 47 failed FEAT jobs. The preparation code tries to read
fMRIPrep confounds before subsequent input checks, so an absent confounds error
does not by itself identify the upstream cause. Doors rows did not carry the
full BIDS/events/BOLD state fields; blank cells are unknown, not absent.

The current local behavior checkout was fast-forwarded to `3b5f05bf6`, then
each of these exact run keys was resolved with `convert_behavior.resolve_sources`
and available sources converted without writing events. There were 40 missing
source resolutions and seven available sources. This checks canonical source
resolution, not every historical commit or mislabeled file in the archive.

The following older supplied workbooks were read without modifying them:
`RF1_MasterSubjectTracker.xlsx`, `RF1_Preprocessing.xlsx`, and
`N318 MRI sessionnotes.xlsx`. Only task-specific evidence is used. Old blanket
QC exclusions and session-02 findings do not become session-01 exclusions.

## Exhaustive Partition

| Evidence category | Runs | Meaning |
| --- | ---: | --- |
| Preserved model exclusion/hold | 3 | Existing model cannot use these runs; do not retry FEAT or clear holds. |
| Explicitly skipped acquisition | 3 | Existing task/session notes state skipped; not missing processing. |
| Known very short Doors acquisition | 1 | No full-task input; not a standard preprocessing retry. |
| Known partial Social Doors acquisition | 1 | Possible partial-run salvage remains unapproved. |
| Historical source contradiction | 3 | Resolve conflicting inventory evidence before claiming absence. |
| Complete behavior, imaging unresolved | 2 | Prioritize source-series/conversion inspection; recovery not yet established. |
| Historical availability gap | 34 | Current absence is corroborated to varying degrees, but not proof of noncollection or an exclusion decision. |
| **Total** | **47** | Includes the one separately recorded UGR hold. |

### Preserved Model Decisions: 3

| Subject | Task/run | Evidence | Action |
| --- | --- | --- | --- |
| 11201 | UGR r1 | Explicit `code/task_availability_holds.tsv` hold; current source has 12 trials and lacks required social-low trials. Master tracker `UGR!A163:F163` explicitly directs run-2-only use. | Preserve run-1 hold; retain run 2 if otherwise eligible. Do not propagate old FD flags. |
| 11125 | Social Doors r1 and Doors r1 (2 rows) | Each current source contains 40 `decision-missed` trials and no `decision` events. Matches the missing canonical decision EV and the existing historical reconciliation. | Unusable for these fixed activation models. Do not invent decision EVs or infer that the participant fell asleep. This does not decide UGR availability. |

### Documented Acquisition Limitations: 5

| Subject | Task/run | Evidence | Action |
| --- | --- | --- | --- |
| 10617, 10690, 10713 | UGR r2 (3 rows) | Master tracker `Wave1vWave2!C7`, `C10`, `C12` says session-01 UGR run 2 was skipped; current BIDS/events/BOLD and canonical behavior are absent. | Record as documented unavailable/skipped, not QC exclusion or processing failure. Preserve run 1. |
| 11203 | Doors r1 | October 1 header audit: 12 instances per echo for magnitude and phase; one behavioral trial, also confirmed in current source. | No full-task input for the current paper model. No routine retry. Counts are DICOM instances, not verified NIfTI volumes. |
| 11203 | Social Doors r1 | October 1 header audit: 187 instances per echo in both parts; current source has 35 trials, including 34 decisions. | Partial-run recovery candidate only. Requires exact timing/image validation and a separate modeling decision; not silently included or declared irrecoverable. |

### Targeted Engineering Follow-Up: 5

| Subject | Task/run | Evidence | Next action |
| --- | --- | --- | --- |
| 10572 | UGR r2 | Master tracker `UGR!D14:F14` and `MRdata!I14` record a second imaging run but missing run-2 behavior; `UGR_225!A300:F300` and current files instead show only run 1. Current canonical raw run-1 (BIDS run 2) behavior is unresolved. | Inspect saved acquisition series and conversion records. Establish whether a second usable UGR series exists before considering processing or another behavior search. Do not call it skipped. |
| 11110 | Social Doors r1 and Doors r1 (2 rows) | Master tracker `MRdata!D152:E152` marks both present, but October 1 exported-source audit found no Doors-like series and no behavior. Session-02 processing is complete and does not resolve this baseline discrepancy. | Compare baseline conversion inventory/export with the historical record. Do not rerun wave 2 or treat its inputs as baseline. |
| 10812 | Social Doors r1 | Complete current 40-trial source (33 decisions, 7 misses); August 31 audit already reported BOLD missing. Master tracker `MRdata!D72` is blank, while Doors in `E72` is present. | Inspect saved series for missing/short/mislabeled acquisition or conversion rejection. Behavior alone does not prove recoverable imaging. |
| 11935 | Doors r1 | Complete current 40-trial source with 40 decisions; August 31 audit already reported BOLD missing. Current preparation stops at missing confounds. | Check BIDS and exact source/conversion series first. This is distinct from the known Social Doors mask/registration investigation; do not assume the same cause. |

### Historical Availability Gaps: 34

| Task/run | Subjects | Rows | Existing evidence and next action |
| --- | --- | ---: | --- |
| UGR r2 | 10603, 10881, 11374, 11439, 11443, 11462, 11679, 11815 | 8 | Current BIDS/events/BOLD and canonical behavior absent. Master tracker records a single run for the first seven (`UGR_225`/`MRdata`); the 11815 preprocessing note addresses localizers, not run-2 noncollection. Review saved series to distinguish no exported acquisition from a conversion omission. Preserve valid run 1. No old FD exclusions reinstated. |
| UGR r1 and r2 | 11085, 11125, 11203, 11396, 11692 | 10 | Both current run slots and canonical behavior absent. Master tracker explicitly says no UGR data for the first four; `MRdata!H269:I269` is empty for 11692. These are availability findings, not newly failed jobs. Inspect inventories if asserting all acquired data have been processed. |
| Social Doors r1 and Doors r1 | 10913, 11075 | 4 | Current behavior unresolved; Social Doors BIDS/events/BOLD absent; Doors input states need checking. Master tracker `MRdata!D97:E97` and `D145:E145` are blank. Baseline inventory check remains needed before calling noncollection settled. |
| Social Doors r1 and Doors r1 | 11083, 11085, 11128, 11145, 11396, 11443 | 12 | October 1 source/conversion audit found no Doors-like exported series; current baseline behavior unresolved. Original notes/archive would distinguish noncollection from unavailable or differently labeled sources. Not a routine FEAT rerun. 11083 session-02 completion is separate and closed. |

## What Is And Is Not Complete

The 557 selected L1 outputs and 271 L2 outputs passed the recorded verification.
The coverage95 selections remain unchanged. This review does not invalidate
those products, certify the omitted source slots as exhaustively resolved,
or change either paper's final survey-linked N.

The first technical follow-up should collect current saved session-01 series
inventories and BIDS/confound presence for these exact subjects into a committed
log. It should not launch preprocessing, reopen settled QC decisions, or ask
Jacob to diagnose source availability. Prioritize 10572, 11110, 10812 and 11935;
retain the separate partial-run review for 11203.

## Supporting Records

- [Full preparation report](../logs/records/no-tedana-unselected-run-review.md)
- [Historical reconciliation](historical-tracker-reconciliation.md#doors-acquisition-reconciliation-2026-10-01)
- [October 1 source audit](../logs/records/20261001-194326_socdoors-missing-source-audit.md)
- [October 1 header/source follow-up](../logs/records/20261001-200328_socdoors-source-followup.md)
- [August 31 events audit](../logs/records/20260831-233156_events-post-team-repairs-20260831-233156.md)
- [Finished no-TEDANA verification](../logs/records/20261021-170903_no-tedana-finish-j20-20261021-170350.md)
