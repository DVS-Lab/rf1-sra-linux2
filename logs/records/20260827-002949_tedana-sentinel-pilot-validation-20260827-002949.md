# Run Record: tedana-sentinel-pilot-validation-20260827-002949

- Timestamp: 20260827-002949
- Branch: main
- Commit: bd6bf883
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20260827-002949_tedana-sentinel-pilot-validation-20260827-002949.log`
- Command exit: 0
- Check exit: 0
- Summary: CHECK PASSED: 16 TEDANA benchmark job(s) validated.

## Command

```bash
env PYTHONUNBUFFERED=1 /ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python benchmark_tedana.py run --sentinel-tsv ../logs/runlists/tedana-sentinel-pilot.tsv --configs t2s-full\,t2s-exclude-nss\,nss-fastica\,nss-robustica --robustica-threads 4 --jobs 4
```

## Check

```bash
env PYTHONUNBUFFERED=1 /ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python benchmark_tedana.py check --sentinel-tsv ../logs/runlists/tedana-sentinel-pilot.tsv --configs t2s-full\,t2s-exclude-nss\,nss-fastica\,nss-robustica --robustica-threads 4
```

## Full Log

```text
RUN START: 20260827-002949
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main bd6bf883
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2/code
COMMAND: env PYTHONUNBUFFERED=1 /ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python benchmark_tedana.py run --sentinel-tsv ../logs/runlists/tedana-sentinel-pilot.tsv --configs t2s-full\,t2s-exclude-nss\,nss-fastica\,nss-robustica --robustica-threads 4 --jobs 4

Queued 16 benchmark job(s) with 4 run-level worker(s); RobustICA receives 4 thread(s) per job.
SKIPPED_COMPLETE t2s-full sub-10785_ses-01_task-sharedreward_run-1
SKIPPED_COMPLETE nss-fastica sub-10785_ses-01_task-sharedreward_run-1
SKIPPED_COMPLETE nss-robustica sub-10785_ses-01_task-sharedreward_run-1
SKIPPED_COMPLETE nss-fastica sub-11068_ses-01_task-sharedreward_run-1
SKIPPED_COMPLETE t2s-exclude-nss sub-10785_ses-01_task-sharedreward_run-1
SKIPPED_COMPLETE t2s-full sub-11068_ses-01_task-sharedreward_run-1
SKIPPED_COMPLETE nss-robustica sub-11068_ses-01_task-sharedreward_run-1
SKIPPED_COMPLETE nss-fastica sub-11560_ses-01_task-doors_run-1
SKIPPED_COMPLETE nss-robustica sub-11560_ses-01_task-doors_run-1
SKIPPED_COMPLETE t2s-exclude-nss sub-11068_ses-01_task-sharedreward_run-1
SKIPPED_COMPLETE t2s-full sub-11560_ses-01_task-doors_run-1
SKIPPED_COMPLETE t2s-exclude-nss sub-11560_ses-01_task-doors_run-1
SKIPPED_COMPLETE t2s-exclude-nss sub-12008_ses-01_task-trust_run-2
SKIPPED_COMPLETE nss-fastica sub-12008_ses-01_task-trust_run-2
SKIPPED_COMPLETE nss-robustica sub-12008_ses-01_task-trust_run-2
SKIPPED_COMPLETE t2s-full sub-12008_ses-01_task-trust_run-2
Completed or previously complete: 16/16
Failures: 0

COMMAND EXIT: 0

CHECK COMMAND: env PYTHONUNBUFFERED=1 /ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python benchmark_tedana.py check --sentinel-tsv ../logs/runlists/tedana-sentinel-pilot.tsv --configs t2s-full\,t2s-exclude-nss\,nss-fastica\,nss-robustica --robustica-threads 4

CHECK PASSED: 16 TEDANA benchmark job(s) validated.

CHECK EXIT: 0
```
