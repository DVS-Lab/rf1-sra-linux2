# Run Record: behavior-source-repair-20260831-232234-sharedreward

- Timestamp: 20260831-232304
- Branch: main
- Commit: 821aea73
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20260831-232304_behavior-source-repair-20260831-232234-sharedreward.log`
- Command exit: 0
- Check exit: 0
- Summary: CHECK PASSED: behavioral BIDS events are internally consistent.

## Command

```bash
bash run_convert_behavior.sh --sublist /ZPOOL/data/projects/rf1-sra-linux2/logs/runlists/behavior-source-repair-20260831-232234-sharedreward.txt --sessions 01 --tasks sharedreward --jobs 4 --overwrite
```

## Check

```bash
python3 check_events.py --sublist /ZPOOL/data/projects/rf1-sra-linux2/logs/runlists/behavior-source-repair-20260831-232234-sharedreward.txt --tasks sharedreward --quiet-ok --review-tsv /ZPOOL/data/projects/rf1-sra-linux2/logs/reviews/behavior-source-repair-20260831-232234-sharedreward.tsv
```

## Full Log

```text
RUN START: 20260831-232304
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main 821aea73
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2/code
COMMAND: bash run_convert_behavior.sh --sublist /ZPOOL/data/projects/rf1-sra-linux2/logs/runlists/behavior-source-repair-20260831-232234-sharedreward.txt --sessions 01 --tasks sharedreward --jobs 4 --overwrite

Using subject list: /ZPOOL/data/projects/rf1-sra-linux2/logs/runlists/behavior-source-repair-20260831-232234-sharedreward.txt
Using private behavior root: /ZPOOL/data/projects/rf1-sra/stimuli
behavior conversion plan: up to 4 subject/session job(s); sessions 01; tasks sharedreward
Launching behavior conversion sub-11969 ses-01
Launching behavior conversion sub-11984 ses-01
Launching behavior conversion sub-12020 ses-01
Launching behavior conversion sub-12021 ses-01
WROTE sub-11969_ses-01_task-sharedreward_run-1_events.tsv: 54 trial(s), 108 event row(s)
WROTE sub-11969_ses-01_task-sharedreward_run-2_events.tsv: 54 trial(s), 108 event row(s)
WROTE sub-12021_ses-01_task-sharedreward_run-1_events.tsv: 54 trial(s), 108 event row(s)
WROTE sub-12021_ses-01_task-sharedreward_run-2_events.tsv: 54 trial(s), 108 event row(s)
WROTE sub-11984_ses-01_task-sharedreward_run-1_events.tsv: 54 trial(s), 108 event row(s)
WROTE sub-11984_ses-01_task-sharedreward_run-2_events.tsv: 54 trial(s), 108 event row(s)
WROTE sub-12020_ses-01_task-sharedreward_run-1_events.tsv: 54 trial(s), 108 event row(s)
WROTE sub-12020_ses-01_task-sharedreward_run-2_events.tsv: 54 trial(s), 108 event row(s)
Launching behavior conversion sub-12032 ses-01
Launching behavior conversion sub-12036 ses-01
BOLD MISSING sub-12032 ses-01: no selected task runs
WROTE sub-12036_ses-01_task-sharedreward_run-1_events.tsv: 54 trial(s), 108 event row(s)
WROTE sub-12036_ses-01_task-sharedreward_run-2_events.tsv: 54 trial(s), 108 event row(s)

COMMAND EXIT: 0

CHECK COMMAND: python3 check_events.py --sublist /ZPOOL/data/projects/rf1-sra-linux2/logs/runlists/behavior-source-repair-20260831-232234-sharedreward.txt --tasks sharedreward --quiet-ok --review-tsv /ZPOOL/data/projects/rf1-sra-linux2/logs/reviews/behavior-source-repair-20260831-232234-sharedreward.tsv

BOLD MISSING sub-12032_ses-01_task-sharedreward_run-1_events.tsv
BOLD MISSING sub-12032_ses-01_task-sharedreward_run-2_events.tsv
Events audit summary:
  BOLD runs found: 10
  BOLD runs without events files: 0
  behavioral source runs found: 12
  events files found: 10
  OK: 10
  behavior source missing: 0
  BOLD missing: 2
  events missing: 0
  behavior source ambiguous: 0
  conversion failed: 0
  unexpected trial count: 0
  behaviorally poor: 0
  review required: 0
  approved human review: 0
  source note: 0
Events audit by task/session:
  ses-01 task-sharedreward: BOLD=10 BOLD-without-events=0 source=12 events=10 OK=10 source-missing=0 BOLD-missing=2 events-missing=0 ambiguous=0 failed=0 unexpected-count=0 poor=0 review-required=0 approved-review=0
Human-review report: /ZPOOL/data/projects/rf1-sra-linux2/logs/reviews/behavior-source-repair-20260831-232234-sharedreward.tsv (0 row(s))
CHECK PASSED: behavioral BIDS events are internally consistent.

CHECK EXIT: 0
```
