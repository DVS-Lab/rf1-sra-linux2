# Run Record: fmriprep-geometry-xform-metadata-preview

- Timestamp: 20260823-101613
- Branch: main
- Commit: 8eb33c5a
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20260823-101613_fmriprep-geometry-xform-metadata-preview.log`
- Command exit: 2
- Check exit: none
- Summary: COMMAND FAILED: exit 2; no check command was provided.

## Command

```bash
/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python fmriprep_geometry.py repair --audit-json ../logs/geometry/fmriprep-geometry-20260817-145053.json
```

## Error Lines

```text
ERROR: fMRIPrep inventory changed since audit; run a new audit before repair (added=['sub-10929/ses-01/func/sub-10929_ses-01_task-doors_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz', 'sub-10929/ses-01/func/sub-10929_ses-01_task-sharedreward_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz', 'sub-10929/ses-01/func/sub-10929_ses-01_task-sharedreward_run-2_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz', 'sub-10929/ses-01/func/sub-10929_ses-01_task-socialdoors_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz', 'sub-10929/ses-01/func/sub-10929_ses-01_task-trust_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz'], removed=[])
```

## Log Tail

```text
RUN START: 20260823-101613
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main 8eb33c5a
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2/code
COMMAND: /ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python fmriprep_geometry.py repair --audit-json ../logs/geometry/fmriprep-geometry-20260817-145053.json

ERROR: fMRIPrep inventory changed since audit; run a new audit before repair (added=['sub-10929/ses-01/func/sub-10929_ses-01_task-doors_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz', 'sub-10929/ses-01/func/sub-10929_ses-01_task-sharedreward_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz', 'sub-10929/ses-01/func/sub-10929_ses-01_task-sharedreward_run-2_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz', 'sub-10929/ses-01/func/sub-10929_ses-01_task-socialdoors_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz', 'sub-10929/ses-01/func/sub-10929_ses-01_task-trust_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz'], removed=[])

COMMAND EXIT: 2
```
