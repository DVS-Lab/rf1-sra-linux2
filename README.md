# SRPAL data: Data Management and Preprocessing
This repository contains the final code for managing and processing all MR task in our SRPAL project (i.e., MR data for UGR, SocialDoors, Trust, and SharedReward). Note that behavioral data for the tasks are processed in separate repos and that this repo serves fMRI data only. The full dataset will eventually be placed on [OpenNeuro][openneuro]. More information about the project can be found in [Smith et al., 2024, Data in Brief.](https://doi.org/10.1016/j.dib.2024.110810)



## A few prerequisites and recommendations
- Understand BIDS and be comfortable navigating Linux
- Install [FSL](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation)
- Install [miniconda or anaconda](https://stackoverflow.com/questions/45421163/anaconda-vs-miniconda)
- Install PyDeface: `pip install pydeface`
- Make singularity containers for heudiconv (version: 1.3.2), mriqc (version: 24.0.2), and fmriprep (version: 24.1.1).
- Ideally you have HPC and XNAT accounts; below instructions are written as though you have access to both XNAT and HPC, though Linux-version of scripts exist and should be substituted in for HPC-relevant steps.


## Notes on repository organization and files
- Raw DICOMS (an input to heudiconv) are only accessible locally (Smith Lab Linux2: /ZPOOL/data/sourcedata)
- Some of the contents of this repository are not tracked (.gitignore) because the files are large and we do not yet have a nice workflow for datalad. Note that we only track key text files in `bids` and `derivatives`.
- Tracked folders and their contents:
  - `code`: analysis code
  - `derivatives`: stores derivates from our scripts (only key text files)
  - `bids`: contains the standardized "raw" in BIDS format (output of heudiconv; only key text files)


## Downloading Data and Running Preprocessing
```
# Get data via datalad (TO DO)
git clone https://github.com/DVS-Lab/rf1-sra-linux2 ? 
cd rf1-sra-linux2
datalad clone https://github.com/OpenNeuroDatasets/XXXXXX.git bids
# the bids folder is a datalad dataset
# you can get all of the data with the command below:
datalad get sub-*
```

# Step 1: Get data via XNAT (for ongoing collection; see Slab page on XNAT for more details)
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
python downloadXNAT.py
```
Input your XNAT credentials and any new subject data files should download to /ZPOOL/data/sourcedata/sourcedata/rf1-sra

# Step 2: Update your subject lists
You need to manually edit the ```sublist_all``` and ```sublist_new``` text files by adding on your newly downloaded subject IDs to the end of the list.
Here is a helpful [Preprocessing log that you should edit as you preprocess data to note any issues.](https://tuprd.sharepoint.com/:x:/r/sites/TU-CLA-Psych-Smith-Lab/_layouts/15/doc.aspx?sourcedoc=%7B516fedac-572d-4246-8b29-0cb9aef0681d%7D&action=edit) Typically, sublist_new will be used for preprocessing incoming data.

# Step 3: BIDS-ify your data, deface, and run warpkit; two ways to do this
First way (the long way):
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash run_prepdata.sh
# This script launches prepdata-linux2.sh with whatever sublist you tell it to run; note that the script currently runs heudiconv and pydeface, and the portion on MRIQC is commented out as MRIQC is run on the HPC for computing resource considerations.
```
Once this script has successfully run (i.e., bids data for the subjects) you next need to run warpkit. 
```
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash run_warpkit.sh
# This script launches warpkit.sh with whatever sublist you tell it to run (typically will be sublist_new.txt)
```
Once this script has successfully run (i.e., .json files for each task in the bids fmap folders for your sublist), you will transfer the data to the HPC. 
```
cd /ZPOOL/data/projects/rf1-sra-linux2/bids
rsync -avL sub-[insertSubID] hpc:/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/bids/
# Manually type in the subject ID of your new subjects
# Note that "hpc" is to be filled in with whatever your shortcut for hpc is

# OR
rsync -avL sub-* hpc:/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/bids/
# This will take longer as it will re-send over .json files that are later edited in HPC; not a big deal since the next step on HPC will write them over again, don't worry 
```
Second way (the short way):
```
# This script launches the prepdata-linux2.sh script; note that the subject list must be updated to be to 
python rf1_preprocessing_forhpc.py
# This will run for a while, but it will 1) run prepdata (heudiconv and pydeface), 2) run warpkit, and 3) rsync over new subjects' BIDS data into the HPC; output can be checked in the parent repo's rf1_preprocessing_forhpc.log
```
# Step 4: On HPC, amend subject list and run fMRIPrep 
This is a good time to git commit your updated subject lists so then on the HPC, you can pull these subject lists.
Prior to running fMRIPrep, you will need to amend the IntendedFor .json files. 
```
cd /gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/code/
python addIntendedFor-hpc.py
# This script will amend IntendedFor files for each task; this is why it's okay to write over the .json files in the rsync step before
```
Once that completes, now run fMRIPrep. There are 2 versions of fMRIPrep scripts that can be run; fmriprep24-hpc and fmriprep25-hpc
Note that the run script also needs to point to the proper updated subject list:
```
cd /gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/code/
bash run_fmriprep-hpc.sh
# Note that this script is HPC-specific; adjust to non-HPC specific script to run on Linux
# The run script currently has fmriprep25-hpc.sh commented out and only runs fmriprep24-hpc.sh
```
Output of this will go to ```rf1-sra-linux2/derivatives/fmriprep-24/```. You can check if the output exists by running the ```check_fmriprep.sh``` script.
# Step 5: On HPC, run MRIQC
As fMRIPrep is running, you can run MRIQC as it uses the same BIDS input data. Again, make sure it's pointing to updated subject list.
```
cd /gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/code/
bash run_mriqc-hpc.sh
# Note that this script is HPC-specific; adjust to non-HPC specific script to run on Linux
```
# Step 6: On HPC, run TEDANA
Once fMRIPrep output for subjects exists (can check using ```check_fmriprep.sh```), you can now run TEDANA. Again, make sure it's pointing to updated subject list.
```
cd /gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/code/
bash run_tedana-hpc.sh
# Note that this script is HPC-specific; adjust to non-HPC specific script to run on Linux
```
Output of this will go to ```rf1-sra-linux2/derivatives/tedana-24/```. You can check if the output exists by running the ```check_tedana.sh``` script.

# Step 7: On HPC, create TEDANA .tsv files for FSL processing
Once TEDANA has successfully run for your subjects, you can create the .tsv files that FSL uses during L1. 
```
cd /gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/code/
python genTedanaConfounds-hpc.py
# Note that this script is HPC-specific; adjust to non-HPC specific script to run on Linux
# The run script currently has tedana-25 sections commented out and only runs tedana-24
```
Output of this will go to ```rf1-sra-linux2/derivatives/fsl/confounds_tedana-24``` (unless you uncomment tedana-25). 

# Step 8: On HPC, transfer over fmriprep-24 and confounds_tedana-24 data for FSL L1 processing now!
Rsync over these large data files/folders. 
```
cd /gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/derivatives/
rsync -avL fmriprep-24 linux2:/ZPOOL/data/projects/rf1-sra-linux2/derivatives/
# This may take a while, since it is a lot of data; can also individually send over the subjects you need
# Replace "linux2" with whatever your shortcut for linux2 is

cd /gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/derivatives/fsl
rsync -avL confounds_tedana-24 linux2:/ZPOOL/data/projects/rf1-sra-linux2/derivatives/fsl/
# Replace "linux2" with whatever your shortcut for linux2 is
# This should be quicker than fmriprep data transfer; YOU CAN ALSO GIT COMMIT THIS DATA
```

# Step 9: On HPC, concatenate MRIQC data for FSL L3 templates
L3 templates use MRIQC data (i.e., fdmean and tsnr) as mean-centereed covariates. To create the output .csv file with these values, you will need to 1) check that MRIQC data exists for your subjects, 2) run ```extract-metrics.py``` after making necessary adjustments to the script, and 3) ```rsync``` or ```git commit``` the data over to linux2.
```
cd /gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/code/
bash check_mriqc.sh 
# You can amend this script for your specific subject list and/or task(s) of interest
```
If data unexpectedly doesn't exist, re-run the subject through MRIQC. Please remember that if someone didn't complete a run of a task in the scanner, they won't have data <3

Now amend extract-metrics.py for your use case. You can change the ```sublist_file``` variable to be your custom sublist, the ```tasks``` variable to be only the task(s) you want data for, and the ```output_file``` variable to be whatever name you'd like to give the output .csv file. Once edited, run ```python extract-metrics.py```. Output will write to the ```code``` repo if that is where you launch the script from. You can similarly transfer data over via rsync (as outlined above) or via GitHub. 



## Acknowledgments
This work was supported, in part, by grants from the National Institutes of Health.

[openneuro]: https://openneuro.org/
