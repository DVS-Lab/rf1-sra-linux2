# Audit Closeout Status, 2026-09-27

This reconciliation uses upstream commit `13e97aee`, the September 16 source
inventory, and the September 27 Trust handoff. Earlier tracker summaries are
dated evidence, not a new exclusion list. Passing imaging/events checks does
not establish stimulus identity or demographic coverage.

## Current Actions

September 29 update: the active Shared Reward handoff is scoped to
[three source-validity items](sharedreward-source-validity.md#active-handoff-scope-2026-09-29).
The other RF1 backlog rows are not part of that team request. Data-quality
adjudication, including acquisition/mask coverage, is deferred until after
validation; the coverage row below is historical context, not a current ask.

| Item | What is established | Smallest remaining action |
| --- | --- | --- |
| Participant demographics | Linux2 recovery and verification passed: 352 rows, zero missing age/sex, and coverage of all 343 eligible Trust participants. The September 27 13:14 downstream preflight also passed. | Closed; no new demographic recovery or preflight retry needed. |
| `10657` Shared Reward | Decision settled: exclude run 1, retain run 2. Ryan supplied the session form recording a run-1 deviation and no run-2 deviations; the PI accepted that evidence. | Engineering: propagate and verify the run-1-only exclusion. No photograph or Trust inference; no repeat team question. |
| `10668` Shared Reward | Decision settled: PI accepted the reviewed Trust / Shared Reward A / Shared Reward B reconstruction using the notes, three acquisition episodes and original append order. | Engineering: preserve originals, reassign Trust-labeled run 2 to Shared Reward run 1 with first 255 volumes and A; move the existing Shared Reward acquisition to run 2 with B. Rebuild/validate affected products under the [repair contract](10668-task-reconstruction.md#review-closure-and-engineering-handoff). Not yet applied. |
| `11913`/`11923` | September 29 conversion-provenance review passed: their four canonical Shared Reward runs link to their own source folders via exact series UIDs (25/29 and 25/33). The complete check, including `10668`, passed 5/5. No metadata conflict or cross-folder assignment was found. Late repeated `11923` acquisitions in the September 16 inventory are Trust run 2. | Recorded Shared Reward source-link step complete; no new lab question or correction indicated. Preserve the historical note's unproven exact scope without claiming independent participant-registration proof. See the [verified links](sharedreward-source-validity.md#verified-conversion-links-2026-09-29). |
| `11134`, `11532` Trust | Historical concerns remain documented; the current structural handoff does not adjudicate stimulus eligibility or historical timing validity. | Trust review: resolve the specific stimulus concern for `11134` and verify the timing allegation for `11532` run 2. Do not treat successful structural certification as sign-off. |
| `10881` session 02 | Known partial-brain acquisition; current coverage is approximately 69%, 68%, and 41% for Doors, Social Doors, and UGR. | Task/QC owner: record the acquisition-coverage disposition for these three runs together. No preprocessing retry is indicated by this evidence. |

The six historical tracker rows are therefore not six fresh processing
failures or six requests for the team to repeat its investigation. Some work
is complete, some needs an engineering closeout, and only specific facts or
scientific decisions require human review. Existing unavailable-source cases
remain documented in [behavior-source-repairs.md](behavior-source-repairs.md).

## What the September 16 Inventory Resolves

The [completed source inventory](../logs/records/20260916-000438_sharedreward-source-validity-20260916-000438.md)
read 47,790 headers, yielding 146 series with zero unreadable headers, header
warnings, or missing input groups. Its exit 0 certifies collection, not mapping.

- `10668`: Trust protocol runs 1 and 2 are series 8/9 and 11/12; Shared Reward
  is series 14/15. Each pair is magnitude/phase of one episode, with separate
  SBRefs. There is one Shared Reward-labeled episode in the collected tree,
  not two. Both behavioral segments have the same scheduled design but
  different timing fingerprints and no absolute task timestamps. The inventory
  narrows chronology but cannot identify the synchronized segment by itself.
- `11913`: Shared Reward magnitude/phase pairs are series 25/26 and 29/30.
  `11923`: corresponding pairs are 25/26 and 33/34. Each has 1,020 instances
  per series and BIDS reports 255 volumes for each run.
- `11923`: Trust run 2 has three episode pairs, 41/42 (612 instances per
  series), 56/57 (92), and 60/61 (1,120). These are consistent with interrupted
  attempts followed by a full acquisition. Protocol labels and counts alone
  do not prove which source produced a canonical image.

The inventory searched matching subject folders, not the entire source archive.
It cannot rule out misplaced series elsewhere or an earlier correction of
registration metadata. The private JSON is already on Linux2 under
`work/sharedreward-source-validity-20260916-000438/`; reuse it before collecting
the same headers again. Keep raw dates, identifiers, and sidecars private.

## Historical Entries That Stay Closed

`10677` Shared Reward run 2 has 99.9349% coverage and no imaging outlier in
`qc/run_qc.tsv`. The inspected downstream `sharedreward-aging` analysis-input
QC agrees (99.9350%, no QC flags). The old large-mask-defect note is superseded
by current quantitative evidence. This is a table-based verification, not a
new visual inspection of the mask on Linux2.

Old WarpKit concerns for `10644` and `11723`, repaired appended logs, localizer
questions, and the later issue-queue workbook retain their documented resolved
status. Old MRIQC labels do not become current exclusions. Imaging and response
QC decisions stay with the task owners; source reconciliation does not revise
their policies or rerun TEDANA.

## Missing Participants Table: Code Diagnosis and Recovery

**Implementation follow-up:** `code/participants.py` and the updated
`prepdata.sh`/`check_bids.sh` now implement recovery, future maintenance, and
verification from saved baseline HeuDiConv metadata. See the
[Linux2 recovery commands](../qc/participants/README.md). The diagnosis below
describes the pre-fix behavior. Live execution status is recorded below.
QA-based exclusions are outside this repair.

**Live recovery verified:** the September 27 13:07 installation/check both
passed (352 rows; zero missing age/sex; all 343 eligible Trust participants
covered). The 13:08 preflight failed because base Conda Python could not import
the Trust package. The [13:14 retry](../logs/records/20260927-131417_participants-trust-preflight-20260927-131417.md)
using the Trust interpreter and current source passed canonical-path and
demographics validation (exit 0). This blocker is closed.

The pre-fix `code/prepdata.sh` creates a scratch BIDS dataset and invokes
HeuDiConv there. Installation carries over the session tree, per-session
HeuDiConv metadata, `dataset_description.json`, and task events sidecars.
There is no installation/merge of `participants.tsv` or `participants.json`.
The exit trap deletes the scratch tree. Consequently, any participants table
generated in scratch is discarded. This is a confirmed omission in the code;
it does not prove that an older canonical table existed or was deleted.

`code/check_bids.sh` does not check participant metadata. Its earlier passes
therefore did not test this failure mode. The Trust source/QC export also has
a narrower contract than demographics-dependent analysis. Issue #1 records
the downstream missing-file failure and the required acceptance criteria.

Recovery and prevention must handle these distinct requirements:

1. Locate an authoritative full-cohort demographic source or preserved
   conversion metadata. Establish ID mapping, age units/reference visit, and
   the meaning of sex coding. Do not treat scanner-entered age/sex as verified
   research demographics without checking provenance.
2. Export unique participant rows and a column-definition sidecar, with source
   hashes and explicit coverage/missingness against the current eligible cohort.
   Preserve genuine unknowns. Local historical Shared Reward tables inspected
   here contain only 245 and 212 rows; neither can cover all 343 Trust participants.
3. Fix staged metadata handling and add demographic handoff validation. A safe
   implementation must reconcile existing rows, retain unrelated columns,
   detect conflicts, handle concurrent conversions, and preserve the defined
   age reference across sessions. Copying a one-subject scratch table over the
   cohort table or letting session 02 overwrite baseline age is not acceptable.
4. Run `python3 -m rf1_trust_socialvalue.full_sample preflight` on Linux2 after
   export, then resume the existing downstream gate. No image/event reconversion
   is needed merely to restore this metadata product.

The implemented recovery uses the same scanner-recorded fields saved by
HeuDiConv, with baseline reference time and field definitions in the sidecar.
This establishes provenance for the reconstructed scanner-demographic product,
not independent validation against research records. Live restoration and
downstream preflight are both verified by the operator records.
