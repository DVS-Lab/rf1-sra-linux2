# Run Record: ryan-corrected-continue-20261120-104228-2841956-verify-retirement

- Timestamp: 20261120-104228
- Branch: main
- Commit: 0c4cafba
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-socdoors-psychosocial`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20261120-104228_ryan-corrected-continue-20261120-104228-2841956-verify-retirement.log`
- Command exit: 1
- Check exit: none
- Summary: COMMAND FAILED: exit 1; no check command was provided.

## Command

```bash
/ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/.venv/bin/python /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-corrected-v1/code-bDlZk2bx/code/ryan_seed_localizers.py verify-retirement
```

## Full Log

```text
RUN START: 20261120-104228
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main 0c4cafba
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial
COMMAND: /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/.venv/bin/python /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-corrected-v1/code-bDlZk2bx/code/ryan_seed_localizers.py verify-retirement

Traceback (most recent call last):
  File "/ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-corrected-v1/code-bDlZk2bx/code/ryan_seed_localizers.py", line 217, in <module>
    retirement_check(state)
  File "/ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-corrected-v1/code-bDlZk2bx/code/ryan_seed_localizers.py", line 27, in retirement_check
    raise ValueError(f"No retirement journal. Inspect the last retire log in {state}; no jobs started.")
ValueError: No retirement journal. Inspect the last retire log in /ZPOOL/data/projects/rf1-sra-socdoors-psychosocial/work/wave1-corrected-v1; no jobs started.

COMMAND EXIT: 1
```
