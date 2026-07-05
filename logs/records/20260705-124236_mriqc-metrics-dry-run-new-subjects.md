# Run Record: mriqc-metrics-dry-run-new-subjects

- Timestamp: 20260705-124236
- Branch: codex/repo-cleanup-validation
- Commit: 5908fa9
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/logs/runs/20260705-124236_mriqc-metrics-dry-run-new-subjects.log`
- Command exit: 0
- Check exit: none
- Summary: COMMAND COMPLETED: no check command provided.

## Command

```bash
python3 extract-metrics.py --sublist ../logs/runlists/prepdata-new-20260704.txt --output-file ../derivatives/mriqc-metrics-new-20260704.csv --dry-run
```

## Full Log

```text
RUN START: 20260705-124236
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test
GIT: codex/repo-cleanup-validation 5908fa9
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code
COMMAND: python3 extract-metrics.py --sublist ../logs/runlists/prepdata-new-20260704.txt --output-file ../derivatives/mriqc-metrics-new-20260704.csv --dry-run

Found 24 MRIQC metric rows.
{'subject': '11923', 'session': 'ses-01', 'task': 'ugr', 'run': '1', 'tsnr': '42.399483437649906', 'fd_mean': '0.13476518949861666', 'json_file': '/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_echo-2_part-mag_bold.json'}
{'subject': '11923', 'session': 'ses-01', 'task': 'ugr', 'run': '2', 'tsnr': '40.450282730162144', 'fd_mean': '0.1638228071352801', 'json_file': '/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_echo-2_part-mag_bold.json'}
{'subject': '11923', 'session': 'ses-01', 'task': 'doors', 'run': '1', 'tsnr': '43.450895726680756', 'fd_mean': '0.14239249079001295', 'json_file': '/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc/sub-11923/ses-01/func/sub-11923_ses-01_task-doors_run-1_echo-2_part-mag_bold.json'}
{'subject': '11923', 'session': 'ses-01', 'task': 'socialdoors', 'run': '1', 'tsnr': '43.512031078571454', 'fd_mean': '0.1426604522617538', 'json_file': '/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc/sub-11923/ses-01/func/sub-11923_ses-01_task-socialdoors_run-1_echo-2_part-mag_bold.json'}
{'subject': '11923', 'session': 'ses-01', 'task': 'trust', 'run': '1', 'tsnr': '43.33767070749309', 'fd_mean': '0.13152919868727161', 'json_file': '/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc/sub-11923/ses-01/func/sub-11923_ses-01_task-trust_run-1_echo-2_part-mag_bold.json'}
{'subject': '11923', 'session': 'ses-01', 'task': 'trust', 'run': '2', 'tsnr': '30.59109538141638', 'fd_mean': '0.19209969578994554', 'json_file': '/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc/sub-11923/ses-01/func/sub-11923_ses-01_task-trust_run-2_echo-2_part-mag_bold.json'}
{'subject': '11923', 'session': 'ses-01', 'task': 'sharedreward', 'run': '1', 'tsnr': '42.59152425499633', 'fd_mean': '0.158765794152008', 'json_file': '/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc/sub-11923/ses-01/func/sub-11923_ses-01_task-sharedreward_run-1_echo-2_part-mag_bold.json'}
{'subject': '11923', 'session': 'ses-01', 'task': 'sharedreward', 'run': '2', 'tsnr': '43.61076578311622', 'fd_mean': '0.12713796290035292', 'json_file': '/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc/sub-11923/ses-01/func/sub-11923_ses-01_task-sharedreward_run-2_echo-2_part-mag_bold.json'}
{'subject': '11924', 'session': 'ses-01', 'task': 'ugr', 'run': '1', 'tsnr': '42.385875821113586', 'fd_mean': '0.19489848363800166', 'json_file': '/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc/sub-11924/ses-01/func/sub-11924_ses-01_task-ugr_run-1_echo-2_part-mag_bold.json'}
{'subject': '11924', 'session': 'ses-01', 'task': 'ugr', 'run': '2', 'tsnr': '45.80330044776201', 'fd_mean': '0.18585829850861887', 'json_file': '/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc/sub-11924/ses-01/func/sub-11924_ses-01_task-ugr_run-2_echo-2_part-mag_bold.json'}

COMMAND EXIT: 0
```
