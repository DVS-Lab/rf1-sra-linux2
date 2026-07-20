# Run Record: post-intendedfor-fieldmaps-only-20260713-082348-fmriprep-supplemental-reverse-jobs4

- Timestamp: 20260713-201012
- Branch: main
- Commit: 1e97b314
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20260713-201012_post-intendedfor-fieldmaps-only-20260713-082348-fmriprep-supplemental-reverse-jobs4.log`
- Command exit: 1
- Check exit: none
- Summary: COMMAND FAILED: exit 1; no check command was provided.

## Command

```bash
bash run_fmriprep.sh --sublist ../logs/runlists/post-intendedfor-fieldmaps-only-20260713-082348_fmriprep-supplemental-reverse-20260713-200928.txt --jobs 4
```

## Error Lines

```text
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
	 Report - setting before (/base/derivatives/fmriprep/sub-10668/ses-01/func/sub-10668_ses-01_task-doors_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10668/ses-01/func/sub-10668_ses-01_task-doors_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10668/ses-01/func/sub-10668_ses-01_task-sharedreward_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10668/ses-01/func/sub-10668_ses-01_task-sharedreward_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10668/ses-01/func/sub-10668_ses-01_task-socialdoors_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10668/ses-01/func/sub-10668_ses-01_task-socialdoors_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10668/ses-01/func/sub-10668_ses-01_task-trust_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10668/ses-01/func/sub-10668_ses-01_task-trust_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10668/ses-01/func/sub-10668_ses-01_task-trust_run-2_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10668/ses-01/func/sub-10668_ses-01_task-trust_run-2_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10668/ses-01/func/sub-10668_ses-01_task-ugr_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10668/ses-01/func/sub-10668_ses-01_task-ugr_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10673/ses-01/func/sub-10673_ses-01_task-doors_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10673/ses-01/func/sub-10673_ses-01_task-doors_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10673/ses-01/func/sub-10673_ses-01_task-sharedreward_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10673/ses-01/func/sub-10673_ses-01_task-sharedreward_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10673/ses-01/func/sub-10673_ses-01_task-sharedreward_run-2_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10673/ses-01/func/sub-10673_ses-01_task-sharedreward_run-2_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10673/ses-01/func/sub-10673_ses-01_task-socialdoors_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10673/ses-01/func/sub-10673_ses-01_task-socialdoors_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10673/ses-01/func/sub-10673_ses-01_task-trust_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10673/ses-01/func/sub-10673_ses-01_task-trust_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10673/ses-01/func/sub-10673_ses-01_task-trust_run-2_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10673/ses-01/func/sub-10673_ses-01_task-trust_run-2_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10673/ses-01/func/sub-10673_ses-01_task-ugr_run-1_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10673/ses-01/func/sub-10673_ses-01_task-ugr_run-1_echo-1_part-mag_sbref.nii.gz) images
	 Report - setting before (/base/derivatives/fmriprep/sub-10673/ses-01/func/sub-10673_ses-01_task-ugr_run-2_part-mag_desc-coreg_boldref.nii.gz) and after (/base/bids/sub-10673/ses-01/func/sub-10673_ses-01_task-ugr_run-2_echo-1_part-mag_sbref.nii.gz) images
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
```

## Log Tail

```text
260718-12:09:52,258 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_doors_run_1_echo_1_part_mag_wf.bold_fsLR_resampling_wf.joinnode" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_doors_run_1_echo_1_part_mag_wf/bold_fsLR_resampling_wf/joinnode".
260718-12:09:52,259 nipype.workflow INFO:
	 [Node] Executing "joinnode" <nipype.interfaces.utility.base.IdentityInterface>
260718-12:09:52,260 nipype.workflow INFO:
	 [Node] Finished "joinnode", elapsed time 0.000205s.
260718-12:09:52,260 nipype.workflow INFO:
	 [Node] Executing "joinnode" <nipype.interfaces.utility.base.IdentityInterface>
260718-12:09:52,261 nipype.workflow INFO:
	 [Node] Executing "joinnode" <nipype.interfaces.utility.base.IdentityInterface>
260718-12:09:52,261 nipype.workflow INFO:
	 [Node] Finished "joinnode", elapsed time 0.000128s.
260718-12:09:52,261 nipype.workflow INFO:
	 [Node] Executing "joinnode" <nipype.interfaces.utility.base.IdentityInterface>
260718-12:09:52,261 nipype.workflow INFO:
	 [Node] Finished "joinnode", elapsed time 0.000188s.
260718-12:09:52,262 nipype.workflow INFO:
	 [Node] Finished "joinnode", elapsed time 0.000155s.
260718-12:09:52,262 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_ugr_run_1_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_ugr_run_1_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-12:09:52,262 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_trust_run_1_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_trust_run_1_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-12:09:52,262 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_ugr_run_2_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_ugr_run_2_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-12:09:52,263 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_trust_run_2_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_trust_run_2_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-12:09:52,264 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-12:09:52,264 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-12:09:52,264 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-12:09:52,265 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-12:09:54,291 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_socialdoors_run_1_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_socialdoors_run_1_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-12:09:54,291 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_sharedreward_run_1_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_sharedreward_run_1_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-12:09:54,293 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-12:09:54,293 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-12:09:54,300 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_doors_run_1_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_doors_run_1_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-12:09:54,300 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_sharedreward_run_2_echo_1_part_mag_wf.bold_grayords_wf.gen_cifti" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_sharedreward_run_2_echo_1_part_mag_wf/bold_grayords_wf/gen_cifti".
260718-12:09:54,302 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-12:09:54,302 nipype.workflow INFO:
	 [Node] Executing "gen_cifti" <niworkflows.interfaces.cifti.GenerateCifti>
260718-12:09:56,678 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.413615s.
260718-12:09:56,722 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.457585s.
260718-12:09:57,283 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 5.017545s.
260718-12:09:57,293 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 5.029068s.
260718-12:09:58,449 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.145696s.
260718-12:09:58,461 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.167271s.
260718-12:09:58,793 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_ugr_run_2_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_ugr_run_2_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-12:09:58,796 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-12:09:59,25 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.721604s.
260718-12:09:59,37 nipype.workflow INFO:
	 [Node] Finished "gen_cifti", elapsed time 4.743131s.
260718-12:09:59,290 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_ugr_run_1_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_ugr_run_1_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-12:09:59,299 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-12:09:59,823 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_trust_run_2_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_trust_run_2_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-12:09:59,826 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-12:10:00,353 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_trust_run_1_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_trust_run_1_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-12:10:00,361 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-12:10:01,168 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_socialdoors_run_1_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_socialdoors_run_1_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-12:10:01,173 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-12:10:01,267 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.470846s.
260718-12:10:01,690 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_sharedreward_run_2_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_sharedreward_run_2_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-12:10:01,699 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-12:10:01,892 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.592337s.
260718-12:10:02,637 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.810061s.
260718-12:10:03,0 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_sharedreward_run_1_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_sharedreward_run_1_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-12:10:03,1 nipype.workflow INFO:
	 [Node] Setting-up "fmriprep_25_2_wf.sub_10673_ses_01_wf.bold_ses_01_task_doors_run_1_echo_1_part_mag_wf.carpetplot_wf.conf_plot" in "/scratch/fmriprep_25_2_wf/sub_10673_ses_01_wf/bold_ses_01_task_doors_run_1_echo_1_part_mag_wf/carpetplot_wf/conf_plot".
260718-12:10:03,4 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-12:10:03,4 nipype.workflow INFO:
	 [Node] Executing "conf_plot" <fmriprep.interfaces.confounds.FMRISummary>
260718-12:10:03,303 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.941469s.
260718-12:10:03,666 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.492863s.
260718-12:10:04,380 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.680864s.
260718-12:10:05,408 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.403921s.
260718-12:10:05,861 nipype.workflow INFO:
	 [Node] Finished "conf_plot", elapsed time 2.856951s.
260718-12:10:08,864 nipype.workflow IMPORTANT:
	 fMRIPrep finished successfully!
260718-12:10:08,867 nipype.workflow IMPORTANT:
	 Works derived from this fMRIPrep execution should include the boilerplate text found in <OUTPUT_PATH>/logs/CITATION.md.

COMMAND EXIT: 1
```
