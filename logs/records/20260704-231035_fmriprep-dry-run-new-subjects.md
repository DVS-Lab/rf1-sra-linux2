# Run Record: fmriprep-dry-run-new-subjects

- Timestamp: 20260704-231035
- Branch: codex/repo-cleanup-validation
- Commit: a24deac
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/logs/runs/20260704-231035_fmriprep-dry-run-new-subjects.log`
- Command exit: 0
- Check exit: none
- Summary: COMMAND COMPLETED: no check command provided.

## Command

```bash
bash run_fmriprep.sh --sublist ../logs/runlists/prepdata-new-20260704.txt --jobs 2 --dry-run
```

## Full Log

```text
RUN START: 20260704-231035
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test
GIT: codex/repo-cleanup-validation a24deac
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code
COMMAND: bash run_fmriprep.sh --sublist ../logs/runlists/prepdata-new-20260704.txt --jobs 2 --dry-run

Using subject list: ../logs/runlists/prepdata-new-20260704.txt
fMRIPrep resource plan: up to 2 subject job(s); each gets --nprocs 48, --omp-nthreads 8, --mem 98000 MB
Launching fMRIPrep sub-11923
Launching fMRIPrep sub-11924
fMRIPrep command: singularity run --cleanenv -B /ZPOOL/data/tools/templateflow:/opt/templateflow -B /ZPOOL/data/tools/mplconfigdir:/opt/mplconfigdir -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test:/base -B /ZPOOL/data/tools/licenses:/opts -B /ZPOOL/data/scratch/tug87422/fmriprep-sub-11924:/scratch /ZPOOL/data/tools/fmriprep-25.2.5.simg /base/bids /base/derivatives/fmriprep participant --participant_label 11924 --stop-on-first-crash --nprocs 48 --omp-nthreads 8 --mem 98000 --me-output-echos --output-spaces MNI152NLin6Asym fsLR --cifti-output 91k --bids-filter-file /base/code/fmriprep_config.json --skip-bids-validation --fs-license-file /opts/fs_license.txt --fs-subjects-dir /base/derivatives/freesurfer -w /scratch
Dry run: not launching fMRIPrep.
fMRIPrep command: singularity run --cleanenv -B /ZPOOL/data/tools/templateflow:/opt/templateflow -B /ZPOOL/data/tools/mplconfigdir:/opt/mplconfigdir -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test:/base -B /ZPOOL/data/tools/licenses:/opts -B /ZPOOL/data/scratch/tug87422/fmriprep-sub-11923:/scratch /ZPOOL/data/tools/fmriprep-25.2.5.simg /base/bids /base/derivatives/fmriprep participant --participant_label 11923 --stop-on-first-crash --nprocs 48 --omp-nthreads 8 --mem 98000 --me-output-echos --output-spaces MNI152NLin6Asym fsLR --cifti-output 91k --bids-filter-file /base/code/fmriprep_config.json --skip-bids-validation --fs-license-file /opts/fs_license.txt --fs-subjects-dir /base/derivatives/freesurfer -w /scratch
Dry run: not launching fMRIPrep.
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924.html
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-doors_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-doors_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-sharedreward_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-sharedreward_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-sharedreward_run-2_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-sharedreward_run-2_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-socialdoors_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-socialdoors_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-trust_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-trust_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-trust_run-2_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-trust_run-2_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-ugr_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-ugr_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-ugr_run-2_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-ugr_run-2_part-mag_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924.html
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-doors_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-doors_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-sharedreward_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-sharedreward_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-sharedreward_run-2_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-sharedreward_run-2*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-socialdoors_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-socialdoors_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-trust_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-trust_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-trust_run-2_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-trust_run-2*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-ugr_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-ugr_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-ugr_run-2_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-01/func/sub-11924_ses-01_task-ugr_run-2*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/freesurfer/sub-11924[_ses-*]/scripts/recon-all.done
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11924/ses-*/func/*_space-fsLR_den-91k_bold.dtseries.nii
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923.html
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-doors_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-doors_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-sharedreward_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-sharedreward_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-sharedreward_run-2_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-sharedreward_run-2_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-socialdoors_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-socialdoors_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-trust_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-trust_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-trust_run-2_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-trust_run-2_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-mag_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923.html
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-doors_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-doors_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-sharedreward_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-sharedreward_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-sharedreward_run-2_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-sharedreward_run-2*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-socialdoors_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-socialdoors_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-trust_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-trust_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-trust_run-2_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-trust_run-2*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/freesurfer/sub-11923[_ses-*]/scripts/recon-all.done
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11923/ses-*/func/*_space-fsLR_den-91k_bold.dtseries.nii
Launching fMRIPrep sub-11928
fMRIPrep command: singularity run --cleanenv -B /ZPOOL/data/tools/templateflow:/opt/templateflow -B /ZPOOL/data/tools/mplconfigdir:/opt/mplconfigdir -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test:/base -B /ZPOOL/data/tools/licenses:/opts -B /ZPOOL/data/scratch/tug87422/fmriprep-sub-11928:/scratch /ZPOOL/data/tools/fmriprep-25.2.5.simg /base/bids /base/derivatives/fmriprep participant --participant_label 11928 --stop-on-first-crash --nprocs 48 --omp-nthreads 8 --mem 98000 --me-output-echos --output-spaces MNI152NLin6Asym fsLR --cifti-output 91k --bids-filter-file /base/code/fmriprep_config.json --skip-bids-validation --fs-license-file /opts/fs_license.txt --fs-subjects-dir /base/derivatives/freesurfer -w /scratch
Dry run: not launching fMRIPrep.
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928.html
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-doors_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-doors_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-sharedreward_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-sharedreward_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-sharedreward_run-2_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-sharedreward_run-2_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-socialdoors_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-socialdoors_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-trust_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-trust_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-trust_run-2_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-trust_run-2_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-ugr_run-1_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-ugr_run-1_part-mag_desc-confounds_timeseries.tsv
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-ugr_run-2_echo-1_part-mag_desc-preproc_bold.nii.gz
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-ugr_run-2_part-mag_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928.html
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-doors_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-doors_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-sharedreward_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-sharedreward_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-sharedreward_run-2_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-sharedreward_run-2*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-socialdoors_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-socialdoors_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-trust_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-trust_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-trust_run-2_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-trust_run-2*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-ugr_run-1_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-ugr_run-1*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-ugr_run-2_echo-1*_desc-preproc_bold.nii.gz
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-01/func/sub-11928_ses-01_task-ugr_run-2*_desc-confounds_timeseries.tsv
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/freesurfer/sub-11928[_ses-*]/scripts/recon-all.done
MISSING /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/fmriprep/sub-11928/ses-*/func/*_space-fsLR_den-91k_bold.dtseries.nii

COMMAND EXIT: 0
```
