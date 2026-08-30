# Open Decisions And Run-Disposition Roadmap

This is the durable, non-PHI review queue for decisions that affect canonical
RF1-SRA run eligibility. It records evidence and proposed architecture; it is
not itself an exclusion list and does not authorize changes to BIDS or imaging
derivatives. Add reviewer, date, rationale, and supporting evidence when a
decision is resolved.

## Current Evidence Snapshot

As of 2026-08-26:

- `qc/run_qc.tsv` inventories 2,729 acquired runs: 2,232 pass the cohort imaging
  rules, 490 have one or more Tukey outlier flags, and 7 are incomplete. These
  are measurements, not automatic exclusions.
- `qc/events/results/run_response_qc.tsv` inventories 2,718 events runs: 2,686
  pass the descriptive response rules and 32 require review. Twenty-five cross
  the current 25% miss threshold, 11 have a terminal miss streak, and 7 meet
  the descriptive salvage-candidate rule.
- `docs/behavior-source-repairs.md` lists 18 missing behavioral sources and one
  unresolved Trust mapping. Events must not be synthesized for these 19 runs.
- Technical repairs for fMRIPrep geometry, `sub-10585`, `sub-11891`,
  `sub-12018`, and the `sub-10929` fieldmap exception are complete and
  provenance-preserving. They should not be reopened without new evidence.

## Settled Data-Governance Policy

The private
`/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions` directory is the
authoritative participant-level exclusion source. Standard analysis and
OpenNeuro release builders must omit every participant represented there,
regardless of residual BIDS or derivative outputs. Residual outputs may remain
preserved locally but do not establish eligibility. Any future reuse requires
deliberate PI and data-governance review.

These exclusions reflect incidental findings. Public documentation and release
reporting must state only the aggregate number excluded for this reason, with
the number calculated from the final release cohort. Do not publish diagnoses,
detailed findings, or participant-by-participant reason associations. No
additional public subject-level rationale is required, and this policy is not
an open scientific adjudication question.

## Settled Technical And Task Decisions

- `10929` session 01 UGR run 2 has a complete magnitude series but an
  unrecoverably short phase series in the available source (92 phase DICOMs
  versus 960 magnitude DICOMs). The reviewed `warpkit_reuse.tsv` exception
  reuses the UGR run-1 WarpKit fieldmap while retaining the run-2 magnitude
  reference. WarpKit and fMRIPrep passed after the repair, and current TEDANA
  auditing finds all seven available `10929` runs complete. Retain UGR run 2
  as technically processed with an explicit acquisition/fieldmap-reuse flag;
  do not treat the absent run-specific phase series as an unresolved pipeline
  failure.
- `11539` received the wrong friend image. This invalidates both Shared Reward
  runs and Trust run 1 for their respective task analyses. Preserve the data
  and provenance locally, but mark those three runs excluded in the canonical
  run-disposition contract. Trust run 2 is not implicated by the available
  note.
- The active models intentionally use corrected canonical UGR cue timing,
  actual Trust feedback duration, and the current Shared Reward miss handling
  and 14-EV model. These conventions are settled and do not require further
  sign-off before downstream processing.

## Decisions Requiring Team Review

### Conversion Versus Behavioral QC

The current converter requires hash-bound approval before writing a coherent
short run or behaviorally poor run. The response-QC layer can now represent
those facts independently. The proposed rule is:

> Write an events file when its source is uniquely mapped, structurally
> readable, and safely interpretable. Record short, poor, or suspicious
> behavior in response QC and adjudicate it in run disposition.

Ambiguous provenance, appended run segments, malformed executed rows, and
unsafe timing remain hard conversion failures. Before changing the converter,
the team must approve this boundary and decide how existing entries in
`code/behavior_curation.tsv` will be preserved as historical review provenance.

`11407` appears to have completed only the mock/localizer visit and remains
unavailable unless new source data are found. The `12018` malformed downloaded
source path has been handled and is no longer an open source-data issue.

### Response Policy And Terminal Failures

The lab must lock down:

- whether the miss criterion is `>=25%` or `>25%`;
- whether that criterion applies only to Social Doors/Doors or to every task;
- whether it means automatic exclusion or human review;
- the minimum retained trials, condition counts, and clean-response fraction
  required for a terminal-failure salvage;
- the approved temporal cutoff and derivative provenance required before any
  functional image is trimmed.

The seven current salvage-review candidates are `10608` Shared Reward run 2,
`10777` Shared Reward run 2, `10908` Social Doors run 1, `11902` Shared Reward
run 2, `11984` UGR run 2, `12033` UGR run 2, and `12041` Shared Reward run 1.
Human review should inspect all 32 response-QC review rows, not only these
seven. `11902` has earlier misses in addition to its terminal block, and
`12041` is also a short run; both require particular caution. The current BIDS
inventory gives `12057` seven acquired events runs with zero misses and no
Trust run 2, so the remembered button-box problem needs session-note/source
confirmation rather than an inferred trim.

Until this policy is approved, no BIDS file or imaging derivative should be
trimmed, and every salvage candidate remains `review`.

### Imaging-QC Adjudication

The 490 imaging outlier rows are too numerous to treat as automatic exclusions
without scientific review. The team should decide which metrics are descriptive
sensitivity flags, which patterns require visual inspection, and whether any
combination can justify exclusion. The 7 incomplete rows require technical
resolution or an explicit `unavailable` disposition. The four factual metrics
and their cohort thresholds must remain separate from the final decision.

Final imaging and response-QC adjudication will be performed at the task level
after technically valid downstream outputs have been inventoried. These review
flags do not block manifest construction, EV generation, or technically valid
first-level processing in the meantime. Refresh the counts above before that
review because the current evidence snapshot predates the newest sessions.

### Acquisition And Task Exceptions

- `11116` session 02 was acquired across two visits separated by roughly one or
  two weeks. The return folder `Smith-SRA-11116-2-socialdoors` was intended to
  complete the missing Social Doors/Doors portion of the same scientific
  session and remains
  `ses-02`, not `ses-03`. The reviewed `supplemental_sources.tsv` row preserves
  the planned temporary merge of both immutable source folders, but its
  `paused` status blocks conversion. The currently tracked private behavior
  logs are the failed August 25 attempts: faces has four trials, Doors has one,
  and neither timing record reached `RunStatus: completed`. Recover and
  timestamp-match the completed post-fix behavior files before activating the
  manifest row. Multiple T1w acquisitions will then receive `run-1`/`run-2`
  entities and all be defaced. This corrects the earlier note that mistakenly
  named `11078`.
- The 18 missing event sources and unresolved `12037` Trust mapping remain the
  authoritative source-repair queue in `docs/behavior-source-repairs.md`.

### Downstream Contract

The four active RF1 task repositories should eventually discover candidate
runs, verify technical inputs, join a versioned Linux2 disposition table, and
then apply only analysis-specific eligibility rules such as requiring both runs
for fixed effects or both tasks for a paired contrast. They should not maintain
independent master source exclusions or recompute canonical RF1 QC.

`sharedreward-aging` currently uses a strict `>25%` miss exclusion while Linux2
reports `>=25%` as a review flag. This conflict must be resolved explicitly.
Analysis-specific harmonization, ratings, age, and covariate rules should remain
downstream. Intrinsic RF1 acquisition or task-invalidity decisions should live
in Linux2 and be consumed downstream.

## Proposed Implementation After Review

Keep factual and adjudicated layers separate:

```text
qc/run_qc.tsv                         imaging measurements
qc/events/results/run_response_qc.tsv response measurements
qc/run_disposition_reviews.tsv        reviewed manual decisions only
qc/run_disposition.tsv                generated one-row-per-run contract
```

The generated table should join on `subject + session + task + run`, constrain
final states to `include`, `exclude`, `review`, or `unavailable`, carry reason
codes and review provenance, and fail if an acquired run is missing or appears
more than once. Its checker should also record hashes of the factual QC inputs,
manual review table, policy, and software revision. Downstream manifests should
fail closed when the contract is missing, stale, duplicated, or lacks a
candidate run.

Do not build this as a manually maintained all-in-one spreadsheet. The generated
contract must remain reproducible, while human decisions stay small, explicit,
and reviewable.
