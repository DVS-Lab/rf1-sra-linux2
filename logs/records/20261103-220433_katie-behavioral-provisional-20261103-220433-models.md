# Run Record: katie-behavioral-provisional-20261103-220433-models

- Timestamp: 20261103-220433
- Branch: main
- Commit: 0c4cafba
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-environment-SD/work/behavioral-moderation-release-8e3217ec3d27`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20261103-220433_katie-behavioral-provisional-20261103-220433-models.log`
- Command exit: 0
- Check exit: 0
- Summary: CHECK PASSED: PROVISIONAL exported scores; item scoring remains unverified; eight full-rank N=97 behavioral models; HC3 inference; no neural changes or exclusions.

## Command

```bash
/ZPOOL/data/projects/rf1-sra-environment-SD/work/venv-katie-review-3c9f226e2615/bin/python code/run_behavioral_moderation.py run --project /ZPOOL/data/projects/rf1-sra-environment-SD --data-root /ZPOOL/data/projects/rf1-sra-environment-SD/work/behavioral-moderation-release-8e3217ec3d27 --root /ZPOOL/data/projects/rf1-sra-environment-SD/work/behavioral-moderation-provisional-v1 --provisional
```

## Check

```bash
/ZPOOL/data/projects/rf1-sra-environment-SD/work/venv-katie-review-3c9f226e2615/bin/python code/run_behavioral_moderation.py check --project /ZPOOL/data/projects/rf1-sra-environment-SD --data-root /ZPOOL/data/projects/rf1-sra-environment-SD/work/behavioral-moderation-release-8e3217ec3d27 --root /ZPOOL/data/projects/rf1-sra-environment-SD/work/behavioral-moderation-provisional-v1 --provisional
```

## Full Log

```text
RUN START: 20261103-220433
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main 0c4cafba
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-environment-SD/work/behavioral-moderation-release-8e3217ec3d27
COMMAND: /ZPOOL/data/projects/rf1-sra-environment-SD/work/venv-katie-review-3c9f226e2615/bin/python code/run_behavioral_moderation.py run --project /ZPOOL/data/projects/rf1-sra-environment-SD --data-root /ZPOOL/data/projects/rf1-sra-environment-SD/work/behavioral-moderation-release-8e3217ec3d27 --root /ZPOOL/data/projects/rf1-sra-environment-SD/work/behavioral-moderation-provisional-v1 --provisional

PROVISIONAL: all 97 exported totals retained; item scoring and MSPSS zero coding remain unverified.
PROVISIONAL: all 97 exported totals retained; item scoring and MSPSS zero coding remain unverified.
CHECK PASSED: PROVISIONAL exported scores; item scoring remains unverified; eight full-rank N=97 behavioral models; HC3 inference; no neural changes or exclusions.

COMMAND EXIT: 0

CHECK COMMAND: /ZPOOL/data/projects/rf1-sra-environment-SD/work/venv-katie-review-3c9f226e2615/bin/python code/run_behavioral_moderation.py check --project /ZPOOL/data/projects/rf1-sra-environment-SD --data-root /ZPOOL/data/projects/rf1-sra-environment-SD/work/behavioral-moderation-release-8e3217ec3d27 --root /ZPOOL/data/projects/rf1-sra-environment-SD/work/behavioral-moderation-provisional-v1 --provisional

PROVISIONAL: all 97 exported totals retained; item scoring and MSPSS zero coding remain unverified.
CHECK PASSED: PROVISIONAL exported scores; item scoring remains unverified; eight full-rank N=97 behavioral models; HC3 inference; no neural changes or exclusions.

CHECK EXIT: 0
```
