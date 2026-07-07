# Run Record: prepdata-new-batch

- Timestamp: 20260705-235846
- Branch: main
- Commit: af885951
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2/logs/runs/20260705-235846_prepdata-new-batch.log`
- Command exit: 1
- Check exit: none
- Summary: COMMAND FAILED: exit 1; no check command was provided.

## Command

```bash
bash run_prepdata.sh --sublist sublist-new.txt --jobs 10
```

## Error Lines

```text
	 stdout 2026-07-06T14:50:23.241014:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_part-phase_bold_heudiconv125_e4_ph (80x80x51x240)
INFO: stdout 2026-07-06T14:50:23.241014:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_part-phase_bold_heudiconv125_e4_ph (80x80x51x240)
WARNING: For now not embedding BIDS and info generated .nii.gz itself since sequence produced multiple files
INFO: Converting /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold (960 DICOMs) -> /out/bids/sub-11923/ses-01/func . Converter: dcm2niix . Output types: ('nii.gz',)
	 stdout 2026-07-06T14:50:43.414024:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e1_ph (80x80x51x240)
INFO: stdout 2026-07-06T14:50:43.414024:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e1_ph (80x80x51x240)
	 stdout 2026-07-06T14:50:46.215717:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e2_ph (80x80x51x240)
INFO: stdout 2026-07-06T14:50:46.215717:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e2_ph (80x80x51x240)
	 stdout 2026-07-06T14:50:49.003452:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e4_ph (80x80x51x240)
INFO: stdout 2026-07-06T14:50:49.003452:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e4_ph (80x80x51x240)
	 stdout 2026-07-06T14:50:51.855743:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e3_ph (80x80x51x240)
INFO: stdout 2026-07-06T14:50:51.855743:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e3_ph (80x80x51x240)
WARNING: For now not embedding BIDS and info generated .nii.gz itself since sequence produced multiple files
INFO: Converting /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref (4 DICOMs) -> /out/bids/sub-11923/ses-01/func . Converter: dcm2niix . Output types: ('nii.gz',)
	 stdout 2026-07-06T14:50:54.924872:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e3 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:54.924872:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e3 (80x80x51x1)
	 stdout 2026-07-06T14:50:54.940061:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e4 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:54.940061:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e4 (80x80x51x1)
	 stdout 2026-07-06T14:50:54.955360:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e1 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:54.955360:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e1 (80x80x51x1)
	 stdout 2026-07-06T14:50:54.970595:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e2 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:54.970595:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e2 (80x80x51x1)
WARNING: For now not embedding BIDS and info generated .nii.gz itself since sequence produced multiple files
INFO: Converting /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref (4 DICOMs) -> /out/bids/sub-11923/ses-01/func . Converter: dcm2niix . Output types: ('nii.gz',)
	 stdout 2026-07-06T14:50:55.319337:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e2 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:55.319337:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e2 (80x80x51x1)
	 stdout 2026-07-06T14:50:55.334523:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e4 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:55.334523:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e4 (80x80x51x1)
	 stdout 2026-07-06T14:50:55.349547:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e1 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:55.349547:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e1 (80x80x51x1)
	 stdout 2026-07-06T14:50:55.364836:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e3 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:55.364836:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e3 (80x80x51x1)
WARNING: For now not embedding BIDS and info generated .nii.gz itself since sequence produced multiple files
INFO: Adding "IntendedFor" to the fieldmaps in /out/bids/sub-11923/ses-01.
INFO: Populating template files under /out/bids/
INFO: PROCESSING DONE: {'subject': '11923', 'outdir': '/out/bids/', 'session': '01'}
Defacing /ZPOOL/data/projects/rf1-sra-linux2/bids/sub-11923/ses-01/anat/sub-11923_ses-01_T1w.nii.gz
  /ZPOOL/data/projects/rf1-sra-linux2/bids/sub-11923/ses-01/anat/sub-11923_ses-01_T1w.nii.gz
  /ZPOOL/data/projects/rf1-sra-linux2/bids/sub-11923/ses-01/anat/sub-11923_ses-01_T1w_defaced.nii.gz
Scrubbing /ZPOOL/data/projects/rf1-sra-linux2/bids/sub-11923/ses-01/sub-11923_ses-01_scans.tsv
```

## Log Tail

```text
INFO: stdout 2026-07-06T14:50:43.414024:CSA slice timing based on 2nd volume, 1st volume corrupted (CMRR bug, range 29147.5..30650, TR=1615 ms)
260706-14:50:43,414 nipype.interface INFO:
	 stdout 2026-07-06T14:50:43.414024:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e1_ph (80x80x51x240)
INFO: stdout 2026-07-06T14:50:43.414024:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e1_ph (80x80x51x240)
260706-14:50:46,215 nipype.interface INFO:
	 stdout 2026-07-06T14:50:46.215717:CSA slice timing based on 2nd volume, 1st volume corrupted (CMRR bug, range 29175..30677.5, TR=1615 ms)
INFO: stdout 2026-07-06T14:50:46.215717:CSA slice timing based on 2nd volume, 1st volume corrupted (CMRR bug, range 29175..30677.5, TR=1615 ms)
260706-14:50:46,215 nipype.interface INFO:
	 stdout 2026-07-06T14:50:46.215717:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e2_ph (80x80x51x240)
INFO: stdout 2026-07-06T14:50:46.215717:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e2_ph (80x80x51x240)
260706-14:50:49,3 nipype.interface INFO:
	 stdout 2026-07-06T14:50:49.003452:CSA slice timing based on 2nd volume, 1st volume corrupted (CMRR bug, range 29210..30712.5, TR=1615 ms)
INFO: stdout 2026-07-06T14:50:49.003452:CSA slice timing based on 2nd volume, 1st volume corrupted (CMRR bug, range 29210..30712.5, TR=1615 ms)
260706-14:50:49,3 nipype.interface INFO:
	 stdout 2026-07-06T14:50:49.003452:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e4_ph (80x80x51x240)
INFO: stdout 2026-07-06T14:50:49.003452:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e4_ph (80x80x51x240)
260706-14:50:51,855 nipype.interface INFO:
	 stdout 2026-07-06T14:50:51.855743:CSA slice timing based on 2nd volume, 1st volume corrupted (CMRR bug, range 29192.5..30695, TR=1615 ms)
INFO: stdout 2026-07-06T14:50:51.855743:CSA slice timing based on 2nd volume, 1st volume corrupted (CMRR bug, range 29192.5..30695, TR=1615 ms)
260706-14:50:51,855 nipype.interface INFO:
	 stdout 2026-07-06T14:50:51.855743:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e3_ph (80x80x51x240)
INFO: stdout 2026-07-06T14:50:51.855743:Convert 240 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_part-phase_bold_heudiconv767_e3_ph (80x80x51x240)
260706-14:50:54,564 nipype.interface INFO:
	 stdout 2026-07-06T14:50:54.564902:Conversion required 28.204707 seconds (12.538972 for core code).
INFO: stdout 2026-07-06T14:50:54.564902:Conversion required 28.204707 seconds (12.538972 for core code).
260706-14:50:54,585 nipype.workflow INFO:
	 [Node] Finished "convert", elapsed time 28.268182s.
INFO: [Node] Finished "convert", elapsed time 28.268182s.
WARNING: For now not embedding BIDS and info generated .nii.gz itself since sequence produced multiple files
INFO: Converting /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref (4 DICOMs) -> /out/bids/sub-11923/ses-01/func . Converter: dcm2niix . Output types: ('nii.gz',)
260706-14:50:54,744 nipype.workflow INFO:
	 [Node] Setting-up "convert" in "/tmp/dcm2niixd_ziu8k7/convert".
INFO: [Node] Setting-up "convert" in "/tmp/dcm2niixd_ziu8k7/convert".
260706-14:50:54,746 nipype.workflow INFO:
	 [Node] Executing "convert" <nipype.interfaces.dcm2nii.Dcm2niix>
INFO: [Node] Executing "convert" <nipype.interfaces.dcm2nii.Dcm2niix>
260706-14:50:54,924 nipype.interface INFO:
	 stdout 2026-07-06T14:50:54.924872:Chris Rorden's dcm2niiX version v1.0.20240202  (JP2:OpenJPEG) (JP-LS:CharLS) GCC12.2.0 x86-64 (64-bit Linux)
INFO: stdout 2026-07-06T14:50:54.924872:Chris Rorden's dcm2niiX version v1.0.20240202  (JP2:OpenJPEG) (JP-LS:CharLS) GCC12.2.0 x86-64 (64-bit Linux)
260706-14:50:54,925 nipype.interface INFO:
	 stdout 2026-07-06T14:50:54.924872:Found 4 DICOM file(s)
INFO: stdout 2026-07-06T14:50:54.924872:Found 4 DICOM file(s)
260706-14:50:54,925 nipype.interface INFO:
	 stdout 2026-07-06T14:50:54.924872:Slices not stacked: echo varies (TE 49.28, 67.02; echo 3, 4). Use 'merge 2D slices' option to force stacking
INFO: stdout 2026-07-06T14:50:54.924872:Slices not stacked: echo varies (TE 49.28, 67.02; echo 3, 4). Use 'merge 2D slices' option to force stacking
260706-14:50:54,925 nipype.interface INFO:
	 stdout 2026-07-06T14:50:54.924872:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e3 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:54.924872:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e3 (80x80x51x1)
260706-14:50:54,940 nipype.interface INFO:
	 stdout 2026-07-06T14:50:54.940061:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e4 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:54.940061:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e4 (80x80x51x1)
260706-14:50:54,955 nipype.interface INFO:
	 stdout 2026-07-06T14:50:54.955360:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e1 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:54.955360:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e1 (80x80x51x1)
260706-14:50:54,970 nipype.interface INFO:
	 stdout 2026-07-06T14:50:54.970595:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e2 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:54.970595:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-1_sbref_heudiconv128_e2 (80x80x51x1)
260706-14:50:54,981 nipype.interface INFO:
	 stdout 2026-07-06T14:50:54.981409:Conversion required 0.193485 seconds (0.071248 for core code).
INFO: stdout 2026-07-06T14:50:54.981409:Conversion required 0.193485 seconds (0.071248 for core code).
260706-14:50:54,999 nipype.workflow INFO:
	 [Node] Finished "convert", elapsed time 0.25264s.
INFO: [Node] Finished "convert", elapsed time 0.25264s.
WARNING: For now not embedding BIDS and info generated .nii.gz itself since sequence produced multiple files
INFO: Converting /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref (4 DICOMs) -> /out/bids/sub-11923/ses-01/func . Converter: dcm2niix . Output types: ('nii.gz',)
260706-14:50:55,134 nipype.workflow INFO:
	 [Node] Setting-up "convert" in "/tmp/dcm2niix9xc0rg3w/convert".
INFO: [Node] Setting-up "convert" in "/tmp/dcm2niix9xc0rg3w/convert".
260706-14:50:55,136 nipype.workflow INFO:
	 [Node] Executing "convert" <nipype.interfaces.dcm2nii.Dcm2niix>
INFO: [Node] Executing "convert" <nipype.interfaces.dcm2nii.Dcm2niix>
260706-14:50:55,319 nipype.interface INFO:
	 stdout 2026-07-06T14:50:55.319337:Chris Rorden's dcm2niiX version v1.0.20240202  (JP2:OpenJPEG) (JP-LS:CharLS) GCC12.2.0 x86-64 (64-bit Linux)
INFO: stdout 2026-07-06T14:50:55.319337:Chris Rorden's dcm2niiX version v1.0.20240202  (JP2:OpenJPEG) (JP-LS:CharLS) GCC12.2.0 x86-64 (64-bit Linux)
260706-14:50:55,319 nipype.interface INFO:
	 stdout 2026-07-06T14:50:55.319337:Found 4 DICOM file(s)
INFO: stdout 2026-07-06T14:50:55.319337:Found 4 DICOM file(s)
260706-14:50:55,319 nipype.interface INFO:
	 stdout 2026-07-06T14:50:55.319337:Slices not stacked: echo varies (TE 31.54, 67.02; echo 2, 4). Use 'merge 2D slices' option to force stacking
INFO: stdout 2026-07-06T14:50:55.319337:Slices not stacked: echo varies (TE 31.54, 67.02; echo 2, 4). Use 'merge 2D slices' option to force stacking
260706-14:50:55,319 nipype.interface INFO:
	 stdout 2026-07-06T14:50:55.319337:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e2 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:55.319337:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e2 (80x80x51x1)
260706-14:50:55,334 nipype.interface INFO:
	 stdout 2026-07-06T14:50:55.334523:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e4 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:55.334523:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e4 (80x80x51x1)
260706-14:50:55,349 nipype.interface INFO:
	 stdout 2026-07-06T14:50:55.349547:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e1 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:55.349547:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e1 (80x80x51x1)
260706-14:50:55,364 nipype.interface INFO:
	 stdout 2026-07-06T14:50:55.364836:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e3 (80x80x51x1)
INFO: stdout 2026-07-06T14:50:55.364836:Convert 1 DICOM as /out/bids/sub-11923/ses-01/func/sub-11923_ses-01_task-ugr_run-2_sbref_heudiconv066_e3 (80x80x51x1)
260706-14:50:55,375 nipype.interface INFO:
	 stdout 2026-07-06T14:50:55.375625:Conversion required 0.198057 seconds (0.070654 for core code).
INFO: stdout 2026-07-06T14:50:55.375625:Conversion required 0.198057 seconds (0.070654 for core code).
260706-14:50:55,393 nipype.workflow INFO:
	 [Node] Finished "convert", elapsed time 0.256867s.
INFO: [Node] Finished "convert", elapsed time 0.256867s.
WARNING: For now not embedding BIDS and info generated .nii.gz itself since sequence produced multiple files
INFO: Adding "IntendedFor" to the fieldmaps in /out/bids/sub-11923/ses-01.
INFO: Populating template files under /out/bids/
INFO: PROCESSING DONE: {'subject': '11923', 'outdir': '/out/bids/', 'session': '01'}
Defacing /ZPOOL/data/projects/rf1-sra-linux2/bids/sub-11923/ses-01/anat/sub-11923_ses-01_T1w.nii.gz
/usr/local/fsl/lib/python3.12/site-packages/pydeface/__main__.py:6: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
  from pkg_resources import require
--------------
pydeface 2.0.2
--------------
Temporary files:
  /tmp/tmpt5g1jnzv.mat
  /tmp/tmpl6r3u1fu.nii.gz
Defacing...
  /ZPOOL/data/projects/rf1-sra-linux2/bids/sub-11923/ses-01/anat/sub-11923_ses-01_T1w.nii.gz
Defaced image saved as:
  /ZPOOL/data/projects/rf1-sra-linux2/bids/sub-11923/ses-01/anat/sub-11923_ses-01_T1w_defaced.nii.gz
Cleaning up...
Finished.
Scrubbing /ZPOOL/data/projects/rf1-sra-linux2/bids/sub-11923/ses-01/sub-11923_ses-01_scans.tsv

COMMAND EXIT: 1
```
