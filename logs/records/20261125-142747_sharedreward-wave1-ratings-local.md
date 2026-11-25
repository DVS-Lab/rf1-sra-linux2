# Run Record: sharedreward-wave1-ratings-local

- Timestamp: 20261125-142747
- Branch: main
- Commit: 5b897768
- Host: CLA19733
- User: tug87422
- Working directory: `/Users/tug87422/github/rf1-sra-linux2`
- Raw log: `/Users/tug87422/github/rf1-sra-linux2/logs/runs/20261125-142747_sharedreward-wave1-ratings-local.log`
- Command exit: 0
- Check exit: 0
- Summary: CHECK PASSED: 334 files verified.

## Command

```bash
python3 code/sharedreward_ratings.py --local-snapshot --apply
```

## Check

```bash
python3 code/sharedreward_ratings.py --local-snapshot --check
```

## Full Log

```text
RUN START: 20261125-142747
PROJECT_ROOT: /Users/tug87422/github/rf1-sra-linux2
GIT: main 5b897768
HOST: CLA19733
USER: tug87422
PWD: /Users/tug87422/github/rf1-sra-linux2
COMMAND: python3 code/sharedreward_ratings.py --local-snapshot --apply

{"ratings_qc_pass": 286, "responses": 1980, "roster": 352, "statuses": {"complete": 330, "missing_source": 22}, "superseded_blocks": 5, "unlinked_source_ids": 3}
CHECK PASSED: 334 files verified.

COMMAND EXIT: 0

CHECK COMMAND: python3 code/sharedreward_ratings.py --local-snapshot --check

{"ratings_qc_pass": 286, "responses": 1980, "roster": 352, "statuses": {"complete": 330, "missing_source": 22}, "superseded_blocks": 5, "unlinked_source_ids": 3}
CHECK PASSED: 334 files verified.

CHECK EXIT: 0
```
