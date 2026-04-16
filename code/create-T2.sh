#!/bin/bash
# copy_flair_to_t2w.sh
# Copies FLAIR .nii.gz and .json files to T2w equivalents
# for all subjects matching sub-?????/ses-01/anat/ pattern

BIDS_DIR="/ZPOOL/data/projects/rf1-sra-linux2/bids"

echo "Starting FLAIR → T2w copy..."
echo "BIDS directory: ${BIDS_DIR}"
echo "---"

count=0
skipped=0
errors=0

for anat_dir in "${BIDS_DIR}"/sub-?????/ses-01/anat; do
    # Extract subject ID from path
    sub=$(basename "$(dirname "$(dirname "$anat_dir")")")

    for ext in nii.gz json; do
        src="${anat_dir}/${sub}_ses-01_FLAIR.${ext}"
        dst="${anat_dir}/${sub}_ses-01_T2w.${ext}"

        # Check source exists
        if [[ ! -f "$src" ]]; then
            echo "  [SKIP] Source not found: $src"
            ((skipped++))
            continue
        fi

        # Warn if destination already exists
        if [[ -f "$dst" ]]; then
            echo "  [WARN] Destination already exists, overwriting: $dst"
        fi

        # Copy
        if cp "$src" "$dst"; then
            echo "  [OK]   $src → $dst"
            ((count++))
        else
            echo "  [ERR]  Failed to copy: $src → $dst"
            ((errors++))
        fi
    done
done

echo "---"
echo "Done. Files copied: ${count} | Skipped (missing): ${skipped} | Errors: ${errors}"
