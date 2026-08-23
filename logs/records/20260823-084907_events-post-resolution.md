# Run Record: events-post-resolution-20260823-084907

- Timestamp: 20260823-084907
- Branch: main
- Pipeline commit: `9f9fbe53`
- Private behavior-source commit: `2bbb1db5b`
- Host: `CLA19787.tu.temple.edu`
- Production subject list: `logs/runlists/full-confounds-20260821-203754_production.txt`
- Local raw log: `logs/runs/events-post-resolution-20260823-084907.log`
- Local review table: `logs/reviews/events-post-resolution-20260823-084907.tsv`
- Checker exit: 1 (expected while human-review blockers remain)

## Audit Result

- BOLD runs found: 2,737
- Behavioral source runs found: 2,735
- Events files found and valid: 2,718
- Events missing from resolvable sources: 0
- Ambiguous source selections: 0
- Approved hash-bound human reviews: 10
- Source notes: 738
- Outstanding review rows: 19

The conversion and checker completed every run with a uniquely resolved source.
The nonzero checker exit records unresolved historical inputs; it does not mean
that a generated events file failed validation. The 16 `BOLD MISSING` inventory
messages describe behavior records without matching selected BOLD acquisitions
and are not part of the 19 missing-events blockers.

## Team Review Required

### Missing Shared Reward sources

- `sub-11450` session 01 run 2
- `sub-11969` session 01 run 1
- `sub-11969` session 01 run 2
- `sub-11984` session 01 run 1
- `sub-12020` session 01 run 1
- `sub-12036` session 01 run 2
- `sub-12037` session 01 run 2

### Missing Trust sources

- `sub-10486` session 01 run 2
- `sub-10617` session 01 run 2
- `sub-10668` session 01 run 2
- `sub-10836` session 01 run 1
- `sub-10974` session 01 run 2
- `sub-11432` session 01 run 1
- `sub-11450` session 01 run 1
- `sub-11772` session 01 run 1

### Other missing sources

- Doors: `sub-11461` session 01 run 1
- Doors: `sub-10590` session 02 run 1
- UGR: `sub-10716` session 02 run 1

### Unresolved mapping

- `sub-12037` session 01 Trust run 2 has two complete segments appended to one
  raw run-1 file. No available timestamp or fingerprint evidence identifies the
  segment corresponding to the imaging run. Do not choose a segment without an
  independent source record.

## Resolution Rule

Do not synthesize events or infer a mapping from behavioral quality. Search the
task laptop, acquisition archive, network backups, and historical repository
states for the 18 missing sources. Resolve `sub-12037` with scanner/task timing,
operator notes, or original file metadata. After any source recovery, commit the
private source correction, rerun conversion only for affected subjects, and run
`check_events.py` again against the production list.
