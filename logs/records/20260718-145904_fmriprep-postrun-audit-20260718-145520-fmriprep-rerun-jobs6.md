# Run Record: fmriprep-postrun-audit-20260718-145520-fmriprep-rerun-jobs6

- Timestamp: 20260718-145904
- Branch: main
- Commit: 9dd22466
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20260718-145904_fmriprep-postrun-audit-20260718-145520-fmriprep-rerun-jobs6.log`
- Command exit: 1
- Check exit: skipped
- Summary: CHECK SKIPPED: command failed, so post-run outputs were not validated.

## Command

```bash
bash run_fmriprep.sh --sublist ../logs/runlists/fmriprep-postrun-audit-20260718-145520_fmriprep-rerun.txt --jobs 6
```

## Check

```bash
bash check_fmriprep.sh --sublist ../logs/runlists/fmriprep-postrun-audit-20260718-145520_fmriprep-rerun.txt
```

## Error Lines

```text
	 Report - setting before (/base/derivatives/fmriprep/sub-10317/ses-01/func/sub-10317_ses-01_task-ugr_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10317/ses-01/func/sub-10317_ses-01_task-ugr_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10317/ses-01/func/sub-10317_ses-01_task-ugr_run-2_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10317/ses-01/func/sub-10317_ses-01_task-ugr_run-2_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10369/ses-01/func/sub-10369_ses-01_task-doors_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10369/ses-01/func/sub-10369_ses-01_task-doors_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10369/ses-01/func/sub-10369_ses-01_task-sharedreward_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10369/ses-01/func/sub-10369_ses-01_task-sharedreward_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10369/ses-01/func/sub-10369_ses-01_task-sharedreward_run-2_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10369/ses-01/func/sub-10369_ses-01_task-sharedreward_run-2_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10369/ses-01/func/sub-10369_ses-01_task-socialdoors_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10369/ses-01/func/sub-10369_ses-01_task-socialdoors_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10369/ses-01/func/sub-10369_ses-01_task-trust_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10369/ses-01/func/sub-10369_ses-01_task-trust_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10369/ses-01/func/sub-10369_ses-01_task-ugr_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10369/ses-01/func/sub-10369_ses-01_task-ugr_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10369/ses-01/func/sub-10369_ses-01_task-ugr_run-2_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10369/ses-01/func/sub-10369_ses-01_task-ugr_run-2_echo-1_part-mag_sbref.nii.gz) images
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
	 [Node] Executing "sources" <fmriprep.interfaces.bids.BIDSURI>
CHECK SKIPPED: command failed, so post-run outputs were not validated.
```

## Log Tail

```text
260718-18:12:41,163 nipype.workflow INFO:
	 [Node] Finished "joinnode", elapsed time 0.000131s.
260718-18:12:41,163 nipype.workflow INFO:
	 [Node] Executing "joinnode" <nipype.interfaces.utility.base.IdentityInterface>
260718-18:12:41,163 nipype.workflow INFO:
	 [Node] Finished "joinnode", elapsed time 0.000137s.
260718-18:12:41,163 nipype.workflow INFO:
	 [Node] Finished "joinnode", elapsed time 0.000125s.
260718-18:12:41,163 nipype.workflow INFO:
	 [Node] Finished "joinnode", elapsed time 0.000127s.
260718-18:12:41,163 nipype.workflow INFO:
	 [Node] Finished "joinnode", elapsed time 0.000133s.
260718-18:12:41,164 nipype.workflow INFO:
	 [Node] Executing "joinnode" <nipype.interfaces.utility.base.IdentityInterface>
260718-18:12:41,165 nipype.workflow INFO:
	 [Node] Finished "joinnode", elapsed time 0.000192s.
260718-18:12:43,167 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_ugr_run_2_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_ugr_run_2_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-18:12:43,167 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_ugr_run_1_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_ugr_run_1_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-18:12:43,167 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_socialdoors_run_1_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_socialdoors_run_1_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-18:12:43,168 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_trust_run_1_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_trust_run_1_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-18:12:43,168 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_trust_run_2_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_trust_run_2_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-18:12:43,168 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_sharedreward_run_1_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_sharedreward_run_1_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-18:12:43,168 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_sharedreward_run_2_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_sharedreward_run_2_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-18:12:43,169 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_doors_run_1_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_doors_run_1_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-18:12:43,169 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-18:12:43,169 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-18:12:43,170 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-18:12:43,170 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-18:12:43,170 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-18:12:43,170 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-18:12:43,170 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-18:12:43,171 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-18:12:47,521 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.35127s.
260718-18:12:47,557 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.385466s.
260718-18:12:47,954 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.784159s.
260718-18:12:47,963 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.792714s.
260718-18:12:48,148 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.977475s.
260718-18:12:48,201 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 5.030924s.
260718-18:12:48,569 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 5.399228s.
260718-18:12:48,585 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 5.415051s.
260718-18:12:49,650 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_ugr_run_2_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_ugr_run_2_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-18:12:49,656 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-18:12:50,161 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_ugr_run_1_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_ugr_run_1_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-18:12:50,167 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-18:12:50,705 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_trust_run_2_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_trust_run_2_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-18:12:50,715 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-18:12:51,250 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_trust_run_1_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_trust_run_1_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-18:12:51,257 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-18:12:51,775 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_socialdoors_run_1_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_socialdoors_run_1_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-18:12:51,782 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-18:12:52,213 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.556327s.
260718-18:12:52,304 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_sharedreward_run_2_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_sharedreward_run_2_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-18:12:52,310 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-18:12:52,825 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.657848s.
260718-18:12:52,846 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_sharedreward_run_1_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_sharedreward_run_1_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-18:12:52,852 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-18:12:53,440 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10478_ses_01_wf.bold_ses_01_task_doors_run_1_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10478_ses_01_wf/bold_ses_01_task_doors_run_1_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-18:12:53,455 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-18:12:53,596 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.881214s.
260718-18:12:54,280 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 3.022424s.
260718-18:12:54,410 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.626552s.
260718-18:12:55,177 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.8666460000000002s.
260718-18:12:55,547 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.694357s.
260718-18:12:55,907 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.451338s.
260718-18:12:59,633 nipype.workflow IMPORTANT:
	 fMRIPrep finished successfully!
260718-18:12:59,639 nipype.workflow IMPORTANT:
	 Works derived from this fMRIPrep execution should include the boilerplate text found in <OUTPUT_PATH>/logs/CITATION.md.

COMMAND EXIT: 1

CHECK SKIPPED: command failed, so post-run outputs were not validated.
```
