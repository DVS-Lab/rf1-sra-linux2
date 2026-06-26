#!/bin/bash
set -euo pipefail

standard_img=/ZPOOL/data/projects/rf1-sra-linux2/derivatives/flirt/WM-mask.nii.gz
standard_voxels=$(fslstats "$standard_img" -V | awk '{print $1}')

echo "Subject,Run,Study,StandardVoxels,OverlapVoxels,UncoveredPercent" > mask_coverage_metrics.csv

while read -r flair; do
    [ -z "$flair" ] && continue

    sub=$(echo "$flair" | grep -oP 'sub-\d+')
    sub_id=${sub#sub-}

    if [ ${#sub_id} -eq 3 ]; then
        study="SRNDNA"
    elif [ ${#sub_id} -eq 5 ]; then
        study="RF1"
    else
        study="UNKNOWN"
    fi

    run=$(echo "$flair" | sed -n 's/.*run-\([0-9]\+\).*/\1/p')
    run=${run:-NA}

    participant_bin=$(mktemp --suffix=_bin.nii.gz)
    intersect=$(mktemp --suffix=_intersect.nii.gz)

    fslmaths "$flair" -thr 3 -bin "$participant_bin"
    fslmaths "$standard_img" -mas "$participant_bin" "$intersect"
    overlap_voxels=$(fslstats "$intersect" -V | awk '{print $1}')
    rm -f "$participant_bin" "$intersect"

    if [ "$standard_voxels" -gt 0 ]; then
        uncovered=$(echo "scale=4; (($standard_voxels - $overlap_voxels) / $standard_voxels) * 100" | bc)
    else
        uncovered="NA"
    fi

    echo "$sub,$run,$study,$standard_voxels,$overlap_voxels,$uncovered" >> mask_coverage_metrics.csv

done < /ZPOOL/data/projects/rf1-sra-linux2/derivatives/flirt/mni-flairs.txt

echo "Done. Results saved to mask_coverage_metrics.csv"
