#!/bin/bash

MRIQC_DIR="/ZPOOL/data/projects/rf1-sra-linux2/derivatives/mriqc"
OUT_TSV="flair_iqms.tsv"

mapfile -t json_files < <(find "$MRIQC_DIR" -path "*/ses-01/anat/*_ses-01_T2w.json" | sort)

if [[ ${#json_files[@]} -eq 0 ]]; then
    echo "No FLAIR JSON files found in $MRIQC_DIR"
    exit 1
fi

# IQM keys to extract (MRIQC structural metrics)
IQMs=(cjv cnr efc fber snr wm2max qi_1 qi_2
      inu_med inu_range rpve summary_wm_mean summary_wm_stdv
      summary_gm_mean summary_gm_stdv summary_csf_mean summary_csf_stdv
      fwhm_avg fwhm_x fwhm_y fwhm_z)

# Write header
echo -e "subject\t$(IFS=$'\t'; echo "${IQMs[*]}")" > "$OUT_TSV"

# Write one row per subject
for json in "${json_files[@]}"; do
    sub=$(echo "$json" | grep -oP 'sub-\w+')
    row="$sub"
    for key in "${IQMs[@]}"; do
        val=$(jq -r --arg k "$key" '.[$k] // "NA"' "$json")
        row="${row}\t${val}"
    done
    echo -e "$row" >> "$OUT_TSV"
done

echo "Done: $OUT_TSV (${#json_files[@]} subjects)"
