# SRPAL data: Data Management and Preprocessing
This repository contains the final code for managing and processing all MR task in our SRPAL project (i.e., MR data for UGR, SocialDoors, Trust, and SharedReward). Note that behavioral data for the tasks are processed in separate repos and that this repo serves fMRI data only. The full dataset will eventually be placed on [OpenNeuro][openneuro]. More information about the project can be found in [Smith et al., 2024, Data in Brief.](https://doi.org/10.1016/j.dib.2024.110810)



## A few prerequisites and recommendations
- Understand BIDS and be comfortable navigating Linux
- Install [FSL](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation)
- Install [miniconda or anaconda](https://stackoverflow.com/questions/45421163/anaconda-vs-miniconda)
- Install PyDeface: `pip install pydeface`
- Make singularity containers for heudiconv (version: 1.3.2), mriqc (version: 24.0.2), and fmriprep (version: 25.2.5 and/or 24.1.1).
- Ideally you have Temple XNAT accounts; below instructions are written as though you have access to XNAT. (Note: Though the HPC is now being retired, HPC-compatible versions of the scripts once existed for fmriprep, mriqc, and tedana, as these are especially computationally-intensive and were completed on the HPC when the resource existed. The HPC follows a PBS/Torque environment that uses `qsub` as the job submission command. Noting for the chance that a similar resource exists again or you have access to one.)


## Notes on repository organization and files
- Raw DICOMS (an input to heudiconv) are only accessible locally (Smith Lab Linux2: /ZPOOL/data/sourcedata)
- Some of the contents of this repository are not tracked (.gitignore) because the files are large and we do not yet have a nice workflow for datalad. Note that we only track key text files in `bids` and `derivatives`.
- GitHub tracked folders and their contents:
  - `code`: analysis code
  - `derivatives`: stores derivates from our scripts (only key text files)
  - `bids`: contains the standardized "raw" in BIDS format (output of heudiconv; only key text files)


## For Smith Lab users (short version of scripts to run in order. Please reference once you're familiar with the preprocessing pipeline as outlined below in detail!)
Make sure `sublist_new.txt` is populated ONLY with new subjects to run, append `sublist_all.txt` with any new subjects missing. 
Make sure the below run scripts are pointing to `sublist_new`, and to check that the proper source and/or output repos are pointed to at the top of scripts.
Cross-referencing subjects and noting any issues using the Preprocessing sheet on OneDrive is highly recommended!
1. run_prepdata.sh (toggle MRIQC on prepdata-linux2.sh on or off, or run mriqc at end)
2. run_warpkit.sh
3. addIntendedFor.py
4. run_fmriprep.sh
5. run_tedana.sh
6. genTedanaConfounds.py
7. run_mriqc.sh (if did not before)
8. extract-metrics.py 


## Downloading Data and Running Preprocessing on your Machine (outside users)
```
# Get data via datalad (TO DO)
git clone https://github.com/DVS-Lab/rf1-sra-linux2 
cd rf1-sra-linux2
datalad clone https://github.com/OpenNeuroDatasets/XXXXXX.git bids
# This dataset is `ds005123`, "Social Reward and Nonsocial Reward Processing Across the Adult Lifespan: An Interim Multi-echo fMRI and Diffusion Dataset" 
# the bids folder is a datalad dataset
# you can get all of the data with the command below:
datalad get sub-*
```

### Step: 1 Downloading Data and Running Preprocessing on your Machine (Smith lab users)
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
python downloadXNAT.py
```
Input your XNAT credentials and any new subject data files should download to `/ZPOOL/data/sourcedata/sourcedata/rf1-sra`

### Step 2: Update your subject lists
You need to manually edit the `sublist_all` and `sublist_new` text files by adding on your newly downloaded subject IDs to the end of the list.
Smith lab users: Here is a helpful [Preprocessing log that you should edit as you preprocess data to note any issues.](https://tuprd.sharepoint.com/:x:/r/sites/TU-CLA-Psych-Smith-Lab/_layouts/15/doc.aspx?sourcedoc=%7B516fedac-572d-4246-8b29-0cb9aef0681d%7D&action=edit) Typically, sublist_new will be used for preprocessing incoming data.

### Step 3: BIDS-ify your data (heudiconv), deface (pydeface), and (optional to do at this stage or in the future) run quality check (MRIQC)
On Linux2: 
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash run_prepdata.sh
```
This script launches prepdata-linux2.sh with whatever sublist you indicated for the run file to run on; ideally it is `sublist_new`. The script runs heudiconv, pydeface, and mriqc; if you are in a time pinch, you may comment out the MRIQC portion of the script (Part 3) and run it later, as it is the most computationally intensive of the three. 

### Step 4: Run warpkit

Once this script has successfully run (i.e., BIDS data for the subjects) you next need to run warpkit. 
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash run_warpkit.sh
```
This script launches warpkit.sh with whatever sublist you tell it to run (typically will be `sublist_new`).

### Step 5: Amend IntendedFor .json files 
Prior to running fMRIPrep, you will need to amend the IntendedFor .json files. 
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
python addIntendedFor.py
# This script will amend IntendedFor files for each task
```

### Step 6: Run fMRIPrep
Once that completes, now run fMRIPrep. There are 2 versions of fMRIPrep scripts that can be run; fmriprep24-hpc and fmriprep25-hpc
Note that the run script also needs to point to the proper updated subject list:
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash run_fmriprep.sh
# Note that this script is Linux-specific; adjust to non-Linux specific script if you want to run on HPC/.qsub (see scripts for details)
```
Output of this will go to `rf1-sra-linux2/derivatives/fmriprep/`. You can check if the output exists by running the `check_fmriprep.sh` script.

### Step 7: Run TEDANA
Once fMRIPrep output for subjects exists (can check using `check_fmriprep.sh`), you can now run TEDANA. Again, make sure it's pointing to updated subject list.
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash run_tedana.sh
# Note that this script is Linux-specific; adjust to non-Linux specific script if you want to run on HPC/.qsub (see scripts for details)
```
Output of this will go to `rf1-sra-linux2/derivatives/tedana/`. You can check if the output exists by running the `check_tedana.sh` script.

### Step 8: Create TEDANA .tsv files for FSL processing
Once TEDANA has successfully run for your subjects, you can create the .tsv files that FSL uses during L1. 
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
python genTedanaConfounds.py
```
Output of this will go to `rf1-sra-linux2/derivatives/fsl/confounds_tedana`. 

### Step 9: If you skipped it in step 1, run MRIQC now
As fMRIPrep is running, you can run MRIQC as it uses the same BIDS input data. Again, make sure it's pointing to updated subject list.
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash run_mriqc.sh
```

### Step 10: Concatenate MRIQC data for FSL L3 templates
L3 templates use MRIQC data (i.e., fdmean and tsnr) as mean-centereed covariates. To create the output .csv file with these values, you will need to amend `extract-metrics.py` for your use case. You can change the `sublist_file` variable to be your custom sublist, the `tasks` variable to be only the task(s) you want data for, and the `output_file` variable to be whatever name you'd like to give the output .csv file. Once edited, run `python extract-metrics.py`. Output will write to the `code` repo if that is where you launch the script from. 
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
python extract-metrics.py
# You can amend this script for your specific subject list and/or task(s) of interest, change file output name to be more descriptive, etc.
```
If data in the output .csv unexpectedly doesn't exist, re-run the subject through MRIQC. Please remember that if someone didn't complete a run of a task in the scanner, they won't have data <3

## Acknowledgments
This work was supported, in part, by grants from the National Institutes of Health.

[openneuro]: https://openneuro.org/
