# Run Record: fmriprep-geometry-xforms-20260823-103351-normalize-apply

- Timestamp: 20260823-104410
- Branch: main
- Commit: c2781b7f
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20260823-104410_fmriprep-geometry-xforms-20260823-103351-normalize-apply.log`
- Command exit: 0
- Check exit: none
- Summary: CHECK PASSED: 2737 non-echo MNI152NLin6Asym BOLD file(s) share the modal spatial grid and qform/sform metadata; voxel values were preserved for 9 normalized file(s).

## Command

```bash
/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python fmriprep_geometry.py normalize-xforms --audit-json ../logs/geometry/fmriprep-geometry-xforms-20260823-103351.json --apply
```

## Full Log

```text
RUN START: 20260823-104410
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2
GIT: main c2781b7f
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2/code
COMMAND: /ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python fmriprep_geometry.py normalize-xforms --audit-json ../logs/geometry/fmriprep-geometry-xforms-20260823-103351.json --apply

Audit xform mismatches: 9
Pending metadata normalization: 9
Already normalized and verified: 0
Xform backup root: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep_geometry/xform_originals/fmriprep-geometry-xforms-20260823-103351
Xform provenance root: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep_geometry/xform_repairs/fmriprep-geometry-xforms-20260823-103351
PENDING sub-11909: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-11909/ses-01/func/sub-11909_ses-01_task-sharedreward_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
PENDING sub-12013: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-doors_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
PENDING sub-12013: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-sharedreward_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
PENDING sub-12013: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-sharedreward_run-2_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
PENDING sub-12013: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-socialdoors_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
PENDING sub-12013: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-trust_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
PENDING sub-12013: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-trust_run-2_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
PENDING sub-12013: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-ugr_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
PENDING sub-12013: /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-ugr_run-2_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
NORMALIZED XFORMS /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-11909/ses-01/func/sub-11909_ses-01_task-sharedreward_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
NORMALIZED XFORMS /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-doors_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
NORMALIZED XFORMS /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-sharedreward_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
NORMALIZED XFORMS /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-sharedreward_run-2_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
NORMALIZED XFORMS /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-socialdoors_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
NORMALIZED XFORMS /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-trust_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
NORMALIZED XFORMS /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-trust_run-2_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
NORMALIZED XFORMS /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-ugr_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
NORMALIZED XFORMS /ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep/sub-12013/ses-01/func/sub-12013_ses-01_task-ugr_run-2_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz
CHECK PASSED: 2737 non-echo MNI152NLin6Asym BOLD file(s) share the modal spatial grid and qform/sform metadata; voxel values were preserved for 9 normalized file(s).

COMMAND EXIT: 0
```
