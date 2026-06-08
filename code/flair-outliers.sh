#!/bin/bash

basedir="/ZPOOL/data/projects/rf1-sra-linux2/derivatives"
outlier_sublist="/ZPOOL/data/projects/rf1-sra-linux2/code/flair-outliers.txt"
output="/ZPOOL/data/projects/rf1-sra-linux2/derivatives/flirt/outlier_flairs_4d.nii.gz"

files=""
for sub in $(cat $outlier_sublist); do
    flair="${basedir}/flirt/sub-${sub}/ses-01/anat/sub-${sub}_ses-01_space-MNI152_FLAIR_brain.nii.gz"
    if [ -f "$flair" ]; then
        files="$files $flair"
    else
        echo "Missing: sub-${sub}"
    fi
done

fslmerge -t $output $files
echo "Merged 4D image saved to $output"
