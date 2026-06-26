#!/bin/bash

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
basedir="$(dirname "$scriptdir")"

standard_mask="/usr/local/fsl/data/standard/MNI152_T1_2mm_brain_mask.nii.gz"
output_csv="${basedir}/bet_overlap_results.csv"

echo "subject,voxels_in_brain,voxels_in_mask,percent_covered" > "$output_csv"

for sub in $(cat "${basedir}/code/sublist-new.txt"); do

    brain="${basedir}/derivatives/flirt/sub-${sub}/ses-01/anat/sub-${sub}_ses-01_space-MNI152_FLAIR_brain.nii.gz"

    if [ ! -f "$brain" ]; then
        echo "sub-${sub}: MISSING"
        echo "sub-${sub},NA,NA,NA" >> "$output_csv"
        continue
    fi

    # Count voxels in subject brain mask (non-zero voxels)
    brain_voxels=$(fslstats "$brain" -V | awk '{print $1}')

    # Count voxels in standard mask
    mask_voxels=$(fslstats "$standard_mask" -V | awk '{print $1}')

    # Count overlap (voxels non-zero in both)
    overlap=$(fslmaths "$brain" -bin -mas "$standard_mask" "${basedir}/derivatives/flirt/sub-${sub}/ses-01/anat/tmp_overlap" -odt int && \
              fslstats "${basedir}/derivatives/flirt/sub-${sub}/ses-01/anat/tmp_overlap" -V | awk '{print $1}')

    # Calculate percentage
    percent=$(echo "scale=2; $overlap / $mask_voxels * 100" | bc)

    echo "sub-${sub}: ${percent}% covered"
    echo "sub-${sub},${brain_voxels},${mask_voxels},${percent}" >> "$output_csv"

    # Clean up temp file
    rm -f "${basedir}/derivatives/flirt/sub-${sub}/ses-01/anat/tmp_overlap.nii.gz"

done

echo ""
echo "Done. Results saved to $output_csv"
