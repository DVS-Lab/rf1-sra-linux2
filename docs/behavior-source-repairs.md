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
- `11493` Doors A4 is selected because its ordered trial fingerprint uniquely
  matches the repository's existing canonical Doors events; A2 remains
  preserved as a noncanonical competing source.
- Terminal interrupted rows in `11201` Shared Reward, `11201` Trust, and `12041`
  Shared Reward are omitted only after the interruption when every later row is
  explicitly unrun. Their completed short runs, plus the pre-existing short UGR
  runs and behaviorally poor Doors/Social Doors runs, have hash-bound curation
  entries and retain run-level QC flags.

## Remaining Source Questions

These are missing or still ambiguous private behavior sources, not converter
failures. Do not synthesize events for them. Re-run `check_events.py` on Linux2
after pulling both repositories; that audit is authoritative for the live BIDS
inventory.

- Shared Reward source missing: `11969` runs 1/2; `11984` run 1; `12020` run 1;
  `11450`, `12036`, and `12037` run 2.
- Trust source missing: `10486`, `10617`, `10668`, and `10974` run 2; `10836`,
  `11432`, `11450`, and `11772` run 1.
- Trust mapping unresolved: `12037` run 2 has two complete segments appended to
  one raw run-1 file and no timestamp evidence yet distinguishes them.
- Doors source missing: `11461` session 01 run 1 and `10590` session 02 run 1.
- UGR source missing: `10716` session 02 run 1. The available scan raw run-1 is
  the task's zero-based second run, not BIDS run 1.

These expected blockers replace the earlier undifferentiated 71-row review
count. The Linux2 post-resolution audit on 2026-08-23 confirmed exactly 19
review rows: the 18 missing sources and one unresolved `12037` Trust mapping
listed above. All 2,718 events files that can currently be resolved passed the
checker. See
[`logs/records/20260823-084907_events-post-resolution.md`](../logs/records/20260823-084907_events-post-resolution.md)
for the tracked audit summary.
