# Run Record: mriqc-metrics-new-subjects

- Timestamp: 20260705-124246
- Branch: codex/repo-cleanup-validation
- Commit: 5908fa9
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/logs/runs/20260705-124246_mriqc-metrics-new-subjects.log`
- Command exit: 0
- Check exit: none
- Summary: COMMAND COMPLETED: no check command provided.

## Command

```bash
python3 extract-metrics.py --sublist ../logs/runlists/prepdata-new-20260704.txt --output-file ../derivatives/mriqc-metrics-new-20260704.csv
```

## Full Log

```text
RUN START: 20260705-124246
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test
GIT: codex/repo-cleanup-validation 5908fa9
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code
COMMAND: python3 extract-metrics.py --sublist ../logs/runlists/prepdata-new-20260704.txt --output-file ../derivatives/mriqc-metrics-new-20260704.csv

Found 24 MRIQC metric rows.
Saved MRIQC metrics to: ../derivatives/mriqc-metrics-new-20260704.csv

COMMAND EXIT: 0
```
