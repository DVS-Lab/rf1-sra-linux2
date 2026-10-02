# Historical Tracker Reconciliation

This document reconciles four older lab workbooks against the canonical
RF1-SRA Linux2 inventories and decisions current on 2026-09-11. The workbooks
are historical evidence, not executable policy. They are not copied into this
repository because they contain private operational notes and links.

**2026-09-27 update:** the [audit closeout](audit-status-20260927.md) incorporates
the completed September 16 raw-source inventory, closes the old `10677` mask
claim against current measurements, and diagnoses the separate missing
participant-metadata handoff. The table below preserves historical claims;
use the closeout for current actions and the limits of completed checks.

**2026-09-15 Shared Reward update:** see
[the source-validity follow-up](sharedreward-source-validity.md). It supersedes
the broad Shared Reward questions below: 10657 is run-1-specific with run-2
correction still conditional; 10668 requires raw acquisition/attempt mapping;
11913/11923 requires a source-date/identity audit. Trust is unchanged. Imaging-QC
exclusions belong to Cooper, not this source-validity pass.

Reviewed sources:

- `RF1-SRA_localizer-missing-fieldmap_tracker.xlsx`
- `RF1_MasterSubjectTracker.xlsx`
- `RF1_Preprocessing.xlsx`
- `N318 MRI sessionnotes.xlsx`

The current technical baseline remains complete: `qc/run_qc.tsv` contains
2,761 acquired runs with complete imaging-QC inputs, and
`qc/events/results/run_response_qc.tsv` contains 2,751 internally consistent
events runs. A historical note can still identify a stimulus, identity, or
acquisition-validity problem that these technical checks cannot detect.

## Findings Requiring Confirmation

These items are not represented adequately in the current durable decision
record. They should remain `review` until the lab confirms the exact task,
run, and contrast scope.

| Subject | Historical evidence | Current evidence | Required action |
| --- | --- | --- | --- |
| `10657` | `RF1_MasterSubjectTracker.xlsx`, `Resolved_EVissue!A19:G19`, `SharedReward!B35`, and `Trust!B35` record a friend-identifier problem and historical exclusion of Shared Reward and Trust. | Both Shared Reward and both Trust runs have complete events and imaging outputs, and no current disposition records the historical scientific-validity concern. | Confirm whether the displayed friend identity invalidated both tasks, selected contrasts, or neither. Do not infer validity from technical completeness. |
| `10668` | `Resolved_EVissue!A4:G9`, `SharedReward!B38`, and `Trust!B38` describe cross-computer/cross-task confusion and a historical broad exclusion. | Current documentation treats Trust run 2 as unavailable while retaining Shared Reward run 1 and Trust run 1. | Confirm that the later, narrower disposition supersedes the historical broad exclusion and identify the evidence supporting the retained runs. |
| `11134` | `UGR_225_DD!A153` records a participant-specific friend-stimulus eligibility concern under the historical Trust exclusions. | Both Trust runs are technically complete and currently enter the downstream Trust subject inventory. | Decide whether the concern invalidates both Trust runs, only friend-related contrasts, or no current contrast. Keep the private rationale outside public documentation. |
| `11532` | `Resolved_EVissue!A18:G18` and `Trust!C220/E220` say Trust run 2 had incorrect timing and was historically removed. | Both Trust runs are technically complete and currently contribute to the downstream Trust L2 inventory. | Verify the timing evidence. If authoritative, exclude Trust run 2 and rebuild any L2 result that combined it. |
| `11923` | `RF1_Preprocessing.xlsx`, `NewTBP!K64`, says late scans were collected under `11913` after two scanner interruptions. | Current Linux2 inventories contain separate, technically complete eight-run records for both `11913` and `11923`; no source-identity exception documents the mapping. Private behavior history has separate commits and files for both IDs. | Compare source DICOM study/series timestamps and IDs with the two visit timelines. Document whether any `11923` imaging series originated under the `11913` scanner registration before accepting identity-sensitive analyses. |
| `10881` session 02 | `RF1_MasterSubjectTracker.xlsx`, `Wave1vWave2!B19:L19`, and `RF1_Preprocessing.xlsx`, `NewTBP!K62`, identify the session as a known partial-brain acquisition. | Canonical brain coverage is 68.93% for Doors, 68.24% for Social Doors, and 41.20% for UGR, while session-01 coverage is normal. | Treat all three session-02 runs as a single acquisition-coverage adjudication, not three unrelated Tukey flags. Confirm `exclude` in the run-disposition review table. |

## Historical Notes Already Accounted For

- The `10386`/`10836`, `11344`/`11433`, and later behavioral-ID corrections
  are either encoded in current conversion behavior or documented in
  `docs/behavior-source-repairs.md`. `11433` is present as a complete subject;
  `11344` is absent from the canonical run inventory.
- Historical appended or restarted logs for `10478`, `10858`, `10887`,
  `10926`, and `11058` now produce complete canonical events. These are
  inherited source corrections. Their provenance should be retained, but the
  old workbook rows alone do not justify reopening the mappings.
- Multi-localizer, fieldmap, and interrupted-scan notes for the ten-subject
  localizer tracker, `11815`, and `11891` do not reveal a current technical
  failure. The affected runs have complete outputs and generally normal brain
  coverage; `11891` also has dedicated source-layout handling. This conclusion
  concerns processing completeness, not retrospective visual fieldmap QC.
- Older WarpKit concerns for `10636`, `10638`, `10644`, `11134`, `11164`,
  `11723`, and `11746` are not current blockers. Their fMRIPrep/TEDANA/QC
  outputs are complete and their brain coverage is normal. `11723` Shared
  Reward run 2 has a TEDANA count flag, which remains descriptive rather than
  evidence of a WarpKit failure.
- The compact `N318 MRI sessionnotes.xlsx` workbook restates the August 2026
  issue queue. Its source repairs, exclusions, `10929` fieldmap reuse, and
  unavailable behavioral runs are already captured in current documentation.
  It adds no new technical blocker.

## Deferred QC Evidence

The older trackers contain many motion, miss-rate, and historical L3 cohort
judgments. They should not be imported as automatic exclusions. Several old
UGR invalid-run markers correspond to current response-QC review rows, including
`10836` run 1, `10954` run 1, `11126` run 2, `11201` run 1, and `11316` run 2.
Those rows belong in the later task-level response and imaging-QC adjudication,
not in the acquisition-completeness pass.

## Implementation Consequence

The historical review reinforces the need for a generated canonical
`qc/run_disposition.tsv` backed by a small reviewed decision table. Technical
completeness alone cannot encode stimulus validity, source identity, or known
partial-brain acquisitions. Until that contract exists, downstream group
builders must not treat the current complete inventories as final scientific
eligibility lists.

## Doors Acquisition Reconciliation, 2026-10-01

This is an acquisition/source-availability investigation, not a new QC exclusion
list. It does not reopen the settled Shared Reward reconstruction or authorize
reconversion, relaxed length rules, or partial-run inclusion.

### Why the earlier completion checks did not close this question

`build_run_qc.py:inventory_bids_runs` starts with existing BIDS echo-2 magnitude
BOLD files. Downstream SocDoors readiness requires events, combined BOLD and
confounds, plus model-required trial types. Passing either check certifies its
selected input set, not that every expected acquisition was transferred and
converted. A task with no BIDS image is outside the imaging-QC denominator.
The earlier broad completion language overstated that scope.

The saved September 11 workbook-inspection output in the `rf1-sra-linux2` task
reported `RF1_MasterSubjectTracker.xlsx!SocialDoorsDoors` as empty (zero nonempty
cells). That historical review therefore did not provide a Doors completeness
roster. The original workbook is no longer present at its supplied local path;
this statement is based on the preserved inspection output, not a fresh read.
Notes about UGR missingness must not be repurposed as Doors dispositions.

### Completed evidence collection

- [First source/HeuDiConv audit](../logs/records/20261001-194326_socdoors-missing-source-audit.md):
  nine participants had no Doors-like labels in their matching source folders
  or saved conversion inventories; two had shorter candidate series.
- [Local behavioral inspection](../logs/records/20261001-195955_socdoors-behavior-local.md):
  current source resolution and trial counts, without imaging access.
- [Linux2 follow-up](../logs/records/20261001-200328_socdoors-source-followup.md):
  all saved series for the eleven participants, plus 22,196 DICOM headers for
  11171/11203. Zero unreadable/conflicting files, warnings or duplicate copies.
  These counts establish successful collection, not acquisition completeness.

The 352 participants in upstream imaging QC include 341 with at least one
Doors/SocialDoors imaging run. `11125` has no decision events in either task
(40 missed trials each), leaving 340 model-compatible participants downstream.
That explains the current processing denominator; it is not a sourcedata census.

| Case | Established evidence | Disposition of the investigation / exact next evidence |
| --- | --- | --- |
| `11083` | No session-01 Doors imaging/behavior found. Complete session-02 behavior for both tasks was added in private commit `ec815ce45` on September 1, 2026; the source search found only one participant folder and a session-01 conversion inventory. Commit date is not independent acquisition-date proof. | Open: locate the session-02 experiment/export in the original scanner/XNAT archive or explain its absence. Do not relabel session-02 behavior as session 01. |
| `11171` | Both task logs have 40 trials. Exported SocialDoors magnitude series has 158/159/159/159 unique instances across echoes 1–4, with an SBRef; no corresponding SocialDoors phase series or Doors acquisition found in the inspected folder. | Open: compare series/file counts against the original archive. Current evidence cannot distinguish interrupted acquisition from incomplete export. Do not claim a full run or manufacture missing phase/echo data. |
| `11203` | SocialDoors has 187 unique instances per echo in both magnitude and phase and 35 behavioral trials. Doors has 12 per echo in both parts and one behavioral trial. Both have SBRefs. | Confirmed short source series, consistent with interrupted tasks; no full-length run recovered. SocialDoors partial-run use requires a separate reviewed image/timing validation and modeling decision. Doors is not a full-task input. Counts alone do not establish volume identity or pairing. |
| `11085`, `11110`, `11128`, `11145`, `11317`, `11364`, `11396`, `11443` | No Doors-labeled imaging in the inspected inventories and no source resolved for either session. Inspected subject-labeled scan commits change no files in `Scan-Social_Doors/data`, including under other IDs. | Open: original session notes/export records must distinguish noncollection from unavailable or differently labeled data. Do not record an acquisition failure or exclusion without that evidence. |

Private Git evidence inspected for the last row: `3c2c3ff09`, `1683babf8`,
`866ec82bf`, `4507e0c09`, `7c79dd4a5`, `6d4ae349a`, `2af9edb08`, `d7ec5ce8c`,
`12cbb7db4`, and `8c1517d7f`. Those scan-labeled commits are from 2024–early
2025. `11171` and `11203` task logs were present in their 2024 scan commits
`9b4d29569` and `450c56835`; `11083`'s baseline scan commit `91b7d976c` changed
no Doors files. This is a targeted commit-history check, not proof that data
exist nowhere in Git, on an acquisition computer, or under another registration.

### Remaining authority and access

The original scanner/XNAT archive and original session notes are not accessible
to this local audit. Linux2 SSH authentication failed; Linux2 reports above were
run by the operator and pushed. Repeating the same exported-file inventory
cannot answer whether the original archive has additional data.

Close each case only with a referenced session-note decision, an archive/export
comparison, or recovered and validated inputs. Until then, use explicit
`source reconciliation open`, not `never acquired`, `excluded`, or `all acquired
participants accounted for`. Downstream outputs already completed remain usable
subject to task-owner QC; no cohort-wide rerun is indicated.
