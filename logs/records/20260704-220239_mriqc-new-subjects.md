# Run Record: mriqc-new-subjects

- Timestamp: 20260704-220239
- Branch: codex/repo-cleanup-validation
- Commit: c898f9d
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/logs/runs/20260704-220239_mriqc-new-subjects.log`
- Command exit: 0
- Check exit: 0
- Summary: CHECK PASSED: MRIQC outputs complete for 24 BOLD input(s).

## Command

```bash
bash run_mriqc.sh --sublist ../logs/runlists/prepdata-new-20260704.txt --jobs 2
```

## Check

```bash
bash check_mriqc.sh --sublist ../logs/runlists/prepdata-new-20260704.txt
```
