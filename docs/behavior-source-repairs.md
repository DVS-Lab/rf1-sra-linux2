# Behavioral Source Repairs

This file records historical private-source repairs that affect canonical BIDS
events. Trial-level data remain in the private `rf1-sra` repository.

## Resolved 2026-08-22

- Shared Reward raw run labels are one-based. This is present in the task's
  initial repository commit and agrees with exact ordered-trial matches to
  OpenNeuro `ds005123` version `1.1.3` for the nine overlapping ambiguous cases.
- `11920` Shared Reward runs 1/2 were valid files lacking the `_raw.csv` suffix;
  they were renamed without changing their contents.
- `12021` and `12057` Shared Reward run 1 and `11722` Trust run 0 were restored
  exactly from the parent state before a later scan commit appended another
  subject/run to each file.
- `12011`, `12031`, and `12049` each contained two complete Shared Reward runs
  appended in chronological order under one run-1 filename. They were split
  into run 1 followed by run 2; both resulting runs pass canonical conversion.
- `11719` Trust run 0 contained a short aborted attempt followed by one complete
  run. The complete second segment is the canonical source for BIDS run 1.
- The earlier fingerprint-only selection of `11493` Doors A4 was later shown
  to reflect a mislabeled historical canonical file. The team-confirmed source
  identity correction under 2026-08-31 below supersedes that selection.
- Terminal interrupted rows in `11201` Shared Reward, `11201` Trust, and `12041`
  Shared Reward are omitted only after the interruption when every later row is
  explicitly unrun. Their completed short runs, plus the pre-existing short UGR
  runs and behaviorally poor Doors/Social Doors runs, have hash-bound curation
  entries and retain run-level QC flags.

## Team-Confirmed Repairs Validated 2026-08-31

Ryan Gephart reviewed REDCap session notes, private Git history, and behavioral
logs. Repository commit boundaries independently corroborate the mappings
below. A hash-guarded private-source patch was prepared and every recovered run
passes the canonical converter with its standard trial count and no conversion
review flag. Commit and pull that private patch before Linux2 reconversion:

- `11969` Shared Reward runs 1/2 were committed under nonexistent ID `11696`
  in private commit `d6bb95fa5` (`11969 Scan`).
- `11984` Shared Reward run 1 is the second segment appended to `12057` run 1
  by commit `8eec6038a` (`Scan 11984`); the valid `12057` segment is retained.
- `12020` Shared Reward run 1 is the first segment initially committed under
  `12021` by `33f5e2910` (`12020 Scan`). The second segment appended by
  `e5b1a33fb` (`12021 Scan`) is restored as the actual `12021` run 1.
- `12036` Shared Reward run 2 is the first segment in the appended `12032`
  source, and the second is `12032` run 2. Ryan independently confirmed the
  assignment, so the previously reverted split is now authorized.
- `10836` Trust's sole completed run was entered as operator run 2 and is
  relabeled raw run 0 to map to the sole BIDS run 1.
- `11432` Trust's first attempt was cut; its sole completed source was saved as
  raw run 2 and is relabeled raw run 0 to map to the sole BIDS run 1.
- `11772` Trust run 1 is the second segment appended to `11722` raw run 0 by
  commit `08711d789` (`11772 Scan`); the valid `11722` segment is retained.
- `11461` Doors A4 was committed under `11493` by `eb474b4b6` (`11461 scan`).
  Doors A2 arrived in `e34dd3bbb` (`SRA sub-11493 scan`) and is the corrected
  `11493` source. This supersedes the earlier fingerprint-only A4 assignment.

These repairs recover nine acquired runs. They also correct the corresponding
`12021` and `11493` source identities rather than merely copying files into the
previously missing destinations. No timing or trial values are synthesized.

## Remaining Source Questions

The live 2026-08-30 audit predates the validated source patch and therefore
still reports 19 acquired runs without usable events. After committing the
private patch, reconverting the affected runs, and correcting `11493`, the
expected unresolved/unavailable queue is ten runs:

### Confirmed unavailable or intrinsically invalid

- Shared Reward: `11450` run 2 was not collected on the behavioral computer;
  `12037` run 2 has no available data or session-note evidence.
- Trust: `10486` run 2 ended early and was cut; `10617` run 2 was cut for time;
  `10668` run 2 ran on a separate computer but no behavior source is available;
  `11450` run 1 was cut because the required friend image was unavailable.

These six acquired imaging runs cannot enter event-related task analyses. They
should be represented as unavailable/intrinsically invalid in the canonical
run-disposition contract, not left as recurring pipeline mysteries.

### Still requiring recovery or adjudication

- `10974` Trust run 2 has no session note and no pushed source.
- `12037` Trust run 2 contains two complete appended segments, but no current
  evidence identifies which segment belongs to the acquired run.
- `10590` session 02 Doors (BIDS `task-doors_run-1`, described in visit order as
  the second Social Doors run) has no source or note confirming collection.
- `10716` session 02 UGR run 1 has no recovered raw run-0 source and incomplete
  session notes. The available raw run-1 maps to BIDS run 2.

Do not synthesize events for these four runs. Continue source recovery or make
an explicit run-disposition decision. Re-run `check_events.py` on Linux2 after
pulling both repositories; that audit is authoritative for the live BIDS tree.

These categorized blockers replace the earlier undifferentiated 71-row review
count. The Linux2 audit on 2026-08-30 confirmed 19 acquired runs without usable
events before the nine-run recovery patch. All 2,730 events files that could
then be resolved passed the checker. The checker's narrower `events missing`
category counts only cases where a valid convertible source exists but its
generated file is absent; it does not include source-missing or
conversion-failed runs.
See
[`logs/records/20260823-084907_events-post-resolution.md`](../logs/records/20260823-084907_events-post-resolution.md)
for the tracked audit summary.
