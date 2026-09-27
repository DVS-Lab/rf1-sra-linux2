# Audit Closeout Status, 2026-09-27

This reconciliation uses upstream commit `13e97aee`, the September 16 source
inventory, and the September 27 Trust handoff. Earlier tracker summaries are
dated evidence, not a new exclusion list. Passing imaging/events checks does
not establish stimulus identity or demographic coverage.

## Current Actions

| Item | What is established | Smallest remaining action |
| --- | --- | --- |
| Participant demographics | [Issue #1](https://github.com/DVS-Lab/rf1-sra-linux2/issues/1) reports missing live `bids/participants.tsv`. The September 27 Trust handoff certified 647 structurally valid runs across 343 participants; it did not certify demographics. | Engineering: recover/identify the authoritative full-cohort source, document session-01 age and sex definitions, export with provenance, and pass downstream preflight. See the diagnosis below. |
| `10657` Shared Reward | The September 15 follow-up establishes that the entered friend name was displayed. Ryan identifies run 1; PI agreement to exclude run 1 and retain run 2 remains conditional on run-2 correction. The old metadata-only hypothesis is superseded. | Team: confirm whether the name was corrected before run 2. Then record and propagate the approved run-specific decision. Do not infer a wrong photograph or a Trust exclusion. |
| `10668` Shared Reward | The September 16 raw inventory contains two Trust-labeled acquisition episodes followed by one Shared Reward episode, and two complete behavioral attempts with the same run-1 design. | Team/source review: establish which behavioral attempt was synchronized with the Shared Reward acquisition, including whether the other attempt ran during a Trust-labeled acquisition. Current filename selection of the first segment is not independent evidence. |
| `11913`/`11923` | The collected headers separate the two folders by study, patient-registration token, and acquisition-day token. Each contains two full Shared Reward acquisitions. Late repeated acquisitions in the `11923` inventory are Trust run 2. No mixed registration is evident in the published inventory. | Engineering: inspect the already-collected private JSON to link canonical BIDS images to exact source series and identify the scope of the historical registration note. No new blanket human question or Shared Reward exclusion is justified yet. |
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

The current `code/prepdata.sh` creates a scratch BIDS dataset and invokes
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

This pass documents the diagnosis and remaining work; it does not claim that
the live participants table has been restored or the staging code repaired.
The authoritative demographics source remains to be established.
