#!/bin/bash

# Script to calculate mask coverage metrics for brain masks
# Processes both fmriprep-24 and fmriprep-25

# Set path to standard brain mask
standard_img="$FSLDIR/data/standard/MNI152_T1_2mm_brain_mask.nii.gz"
standard_voxels=$(fslstats "$standard_img" -V | awk '{print $1}')

# Define variables
BASE_PROJECT_DIR="/ZPOOL/data/projects/rf1-sra-linux2"
CODE_DIR="${BASE_PROJECT_DIR}/code"
TEMP_DIR="/tmp/mask_coverage_temp"

# Create temp directory
mkdir -p "${TEMP_DIR}"

# Define fmriprep versions
VERSIONS=("24" "25")

# Define tasks and runs
#TASKS=("ugr" "doors" "socialdoors" "trust" "sharedreward")
TASKS=("doors" "socialdoors")
RUNS=(1)
SESSION="01"

# Single output CSV
OUTPUT_CSV="${CODE_DIR}/mask_coverage_comparison.csv"

echo "Standard brain voxel count: ${standard_voxels}"
echo ""

# Initialize CSV file with headers
echo "Subject,Session,Task,Run,Voxels_fmriprep24,Coverage_fmriprep24,Voxels_fmriprep25,Coverage_fmriprep25,Difference_Voxels,Difference_Coverage" > "${OUTPUT_CSV}"

# Get list of subjects from fmriprep-24 (assuming both versions have same subjects)
BASE_DIR_24="${BASE_PROJECT_DIR}/derivatives/fmriprep-24"
SUBJECTS=($(ls -d ${BASE_DIR_24}/sub-????? 2>/dev/null | xargs -n 1 basename))

if [ ${#SUBJECTS[@]} -eq 0 ]; then
    echo "ERROR: No subjects found in ${BASE_DIR_24}"
    exit 1
fi

echo "Found ${#SUBJECTS[@]} subjects"
echo "Calculating coverage metrics and comparing versions..."
echo ""

# Loop through subjects, tasks, and runs
for SUB in "${SUBJECTS[@]}"; do
    for TASK in "${TASKS[@]}"; do
        for RUN in "${RUNS[@]}"; do
            # Initialize variables for both versions
            mask_voxels_24="NA"
            coverage_24="NA"
            mask_voxels_25="NA"
            coverage_25="NA"
            
            # Process fmriprep-24
            MASK_PATH_24="${BASE_PROJECT_DIR}/derivatives/fmriprep-24/${SUB}/ses-${SESSION}/func/${SUB}_ses-${SESSION}_task-${TASK}_run-${RUN}_part-mag_space-MNI152NLin6Asym_desc-brain_mask.nii.gz"
            
            if [ -f "${MASK_PATH_24}" ]; then
                tmp_mask_24="${TEMP_DIR}/${SUB}_${TASK}_run${RUN}_v24_temp.nii.gz"
                fslmaths "${MASK_PATH_24}" -bin "${tmp_mask_24}" 2>/dev/null
                mask_voxels_24=$(fslstats "${tmp_mask_24}" -V | awk '{print $1}')
                coverage_24=$(echo "scale=4; ($mask_voxels_24 / $standard_voxels) * 100" | bc)
                rm -f "${tmp_mask_24}"
            fi
            
            # Process fmriprep-25
            MASK_PATH_25="${BASE_PROJECT_DIR}/derivatives/fmriprep-25/${SUB}/ses-${SESSION}/func/${SUB}_ses-${SESSION}_task-${TASK}_run-${RUN}_part-mag_space-MNI152NLin6Asym_desc-brain_mask.nii.gz"
            
            if [ -f "${MASK_PATH_25}" ]; then
                tmp_mask_25="${TEMP_DIR}/${SUB}_${TASK}_run${RUN}_v25_temp.nii.gz"
                fslmaths "${MASK_PATH_25}" -bin "${tmp_mask_25}" 2>/dev/null
                mask_voxels_25=$(fslstats "${tmp_mask_25}" -V | awk '{print $1}')
                coverage_25=$(echo "scale=4; ($mask_voxels_25 / $standard_voxels) * 100" | bc)
                rm -f "${tmp_mask_25}"
            fi
            
            # Calculate differences if both exist
            if [ "$mask_voxels_24" != "NA" ] && [ "$mask_voxels_25" != "NA" ]; then
                diff_voxels=$(echo "$mask_voxels_25 - $mask_voxels_24" | bc)
                diff_coverage=$(echo "scale=4; $coverage_25 - $coverage_24" | bc)
            else
                diff_voxels="NA"
                diff_coverage="NA"
            fi
            
            # Only write row if at least one version has data
            if [ "$mask_voxels_24" != "NA" ] || [ "$mask_voxels_25" != "NA" ]; then
                echo "${SUB},ses-${SESSION},${TASK},${RUN},${mask_voxels_24},${coverage_24},${mask_voxels_25},${coverage_25},${diff_voxels},${diff_coverage}" >> "${OUTPUT_CSV}"
                echo "  Processed: ${SUB} - ${TASK} - run ${RUN}"
            fi
        done
    done
done

# Clean up temp directory
rm -rf "${TEMP_DIR}"

echo ""
echo "============================================"
echo "All processing complete!"
echo "============================================"
echo "Results saved to: ${OUTPUT_CSV}"
echo ""
echo "CSV columns:"
echo "  - Voxels_fmriprep24: Voxel count from fmriprep-24"
echo "  - Coverage_fmriprep24: % coverage from fmriprep-24"
echo "  - Voxels_fmriprep25: Voxel count from fmriprep-25"
echo "  - Coverage_fmriprep25: % coverage from fmriprep-25"
echo "  - Difference_Voxels: fmriprep25 - fmriprep24 (voxels)"
echo "  - Difference_Coverage: fmriprep25 - fmriprep24 (% coverage)"
echo ""
echo "Done!"
