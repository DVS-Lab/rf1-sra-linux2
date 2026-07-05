# Run Record: prepdata-new-subjects

- Timestamp: 20260704-204414
- Branch: codex/repo-cleanup-validation
- Commit: 5f45284
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/logs/runs/20260704-204414_prepdata-new-subjects.log`
- Command exit: 0
- Check exit: 0
- Summary: CHECK PASSED: BIDS/prepdata outputs complete for 3 expected session(s).

## Command

```bash
bash run_prepdata.sh --sublist ../logs/runlists/prepdata-new-20260704.txt --jobs 2
```

## Check

```bash
bash check_bids.sh --sublist ../logs/runlists/prepdata-new-20260704.txt
```
