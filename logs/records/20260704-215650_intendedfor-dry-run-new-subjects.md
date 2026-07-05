# Run Record: intendedfor-dry-run-new-subjects

- Timestamp: 20260704-215650
- Branch: codex/repo-cleanup-validation
- Commit: 5f45284
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/logs/runs/20260704-215650_intendedfor-dry-run-new-subjects.log`
- Command exit: 0
- Check exit: none
- Summary: COMMAND COMPLETED: no check command provided.

## Command

```bash
python3 addIntendedFor.py --dry-run
```

## Full Log

```text
RUN START: 20260704-215650
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test
GIT: codex/repo-cleanup-validation 5f45284
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code
COMMAND: python3 addIntendedFor.py --dry-run

SKIP sub-10317/ses-01/fmap/sub-10317_ses-01_acq-bold_magnitude1.json: could not parse task/run
SKIP sub-10317/ses-01/fmap/sub-10317_ses-01_acq-bold_magnitude2.json: could not parse task/run
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-doors_run-1_fieldmap.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-doors_run-1_magnitude.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-sharedreward_run-1_fieldmap.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-sharedreward_run-1_magnitude.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-sharedreward_run-2_fieldmap.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-sharedreward_run-2_magnitude.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-socialdoors_run-1_fieldmap.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-socialdoors_run-1_magnitude.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-trust_run-1_fieldmap.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-trust_run-1_magnitude.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-ugr_run-1_fieldmap.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-ugr_run-1_magnitude.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-ugr_run-2_fieldmap.json: IntendedFor already current
OK   sub-10317/ses-01/fmap/sub-10317_ses-01_acq-ugr_run-2_magnitude.json: IntendedFor already current
SKIP sub-10953/ses-01/fmap/sub-10953_ses-01_acq-bold_magnitude1.json: could not parse task/run
SKIP sub-10953/ses-01/fmap/sub-10953_ses-01_acq-bold_magnitude2.json: could not parse task/run
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-doors_run-1_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-doors_run-1_magnitude.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-sharedreward_run-1_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-sharedreward_run-1_magnitude.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-sharedreward_run-2_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-sharedreward_run-2_magnitude.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-socialdoors_run-1_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-socialdoors_run-1_magnitude.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-trust_run-1_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-trust_run-1_magnitude.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-trust_run-2_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-trust_run-2_magnitude.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-ugr_run-1_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-ugr_run-1_magnitude.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-ugr_run-2_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-01/fmap/sub-10953_ses-01_acq-ugr_run-2_magnitude.json: IntendedFor already current
SKIP sub-10953/ses-02/fmap/sub-10953_ses-02_acq-bold_magnitude.json: could not parse task/run
OK   sub-10953/ses-02/fmap/sub-10953_ses-02_acq-doors_run-1_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-02/fmap/sub-10953_ses-02_acq-doors_run-1_magnitude.json: IntendedFor already current
OK   sub-10953/ses-02/fmap/sub-10953_ses-02_acq-socialdoors_run-1_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-02/fmap/sub-10953_ses-02_acq-socialdoors_run-1_magnitude.json: IntendedFor already current
OK   sub-10953/ses-02/fmap/sub-10953_ses-02_acq-ugr_run-1_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-02/fmap/sub-10953_ses-02_acq-ugr_run-1_magnitude.json: IntendedFor already current
OK   sub-10953/ses-02/fmap/sub-10953_ses-02_acq-ugr_run-2_fieldmap.json: IntendedFor already current
OK   sub-10953/ses-02/fmap/sub-10953_ses-02_acq-ugr_run-2_magnitude.json: IntendedFor already current
SKIP sub-11923/ses-01/fmap/sub-11923_ses-01_acq-bold_magnitude.json: could not parse task/run
SKIP sub-11924/ses-01/fmap/sub-11924_ses-01_acq-bold_magnitude.json: could not parse task/run
SKIP sub-11928/ses-01/fmap/sub-11928_ses-01_acq-bold_magnitude.json: could not parse task/run
SKIP sub-11982/ses-01/fmap/sub-11982_ses-01_acq-bold_magnitude.json: could not parse task/run
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-doors_run-1_fieldmap.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-doors_run-1_magnitude.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-sharedreward_run-1_fieldmap.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-sharedreward_run-1_magnitude.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-sharedreward_run-2_fieldmap.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-sharedreward_run-2_magnitude.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-socialdoors_run-1_fieldmap.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-socialdoors_run-1_magnitude.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-trust_run-1_fieldmap.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-trust_run-1_magnitude.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-trust_run-2_fieldmap.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-trust_run-2_magnitude.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-ugr_run-1_fieldmap.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-ugr_run-1_magnitude.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-ugr_run-2_fieldmap.json: IntendedFor already current
OK   sub-11982/ses-01/fmap/sub-11982_ses-01_acq-ugr_run-2_magnitude.json: IntendedFor already current
would update 0 JSON file(s); skipped 9.

COMMAND EXIT: 0
```
