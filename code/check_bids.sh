#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash check_bids.sh [--sublist FILE]
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

sublist="$BATCH_SUBLIST"
while (($#)); do
  case "$1" in
    --sublist)
      sublist="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

rf1_require_file "$sublist"
bidsroot="${PROJECT_ROOT}/bids"
failed=0
checked=0

if [[ ! -f "${bidsroot}/dataset_description.json" ]]; then
  echo "MISSING ${bidsroot}/dataset_description.json"
  failed=1
fi

source_has_dicoms() {
  local folder_sub="$1"
  local subdir
  if [[ "$folder_sub" == "11891" ]]; then
    subdir="${SOURCEDATA_ROOT}/11891/Smith-SRA-11891/Smith-SRA-11891"
  else
    subdir="${SOURCEDATA_ROOT}/Smith-SRA-${folder_sub}/Smith-SRA-${folder_sub}"
  fi
  [[ -d "$subdir" ]] || return 1
  find "${subdir}/scans" -type f -name '*.dcm' -print -quit 2>/dev/null | grep -q .
}

while IFS= read -r sub; do
  for ses in 01 02; do
    folder_sub="$sub"
    [[ "$ses" == "02" ]] && folder_sub="${sub}-2"
    if ! source_has_dicoms "$folder_sub"; then
      if [[ "$ses" == "02" ]]; then
        echo "SKIP sub-${sub} ses-${ses}: no optional source DICOMs found"
        continue
      fi
      echo "MISSING source DICOMs for required sub-${sub} ses-${ses}"
      failed=1
      continue
    fi

    checked=$((checked + 1))
    session_dir="${bidsroot}/sub-${sub}/ses-${ses}"
    scans_tsv="${session_dir}/sub-${sub}_ses-${ses}_scans.tsv"
    if [[ ! -d "$session_dir" ]]; then
      echo "MISSING $session_dir"
      failed=1
      continue
    fi
    if [[ ! -f "$scans_tsv" ]]; then
      echo "MISSING $scans_tsv"
      failed=1
    elif grep -Eq $'\t20[0-9][0-9]-' "$scans_tsv"; then
      echo "UNSHIFTED $scans_tsv still contains modern acquisition dates"
      failed=1
    fi
    if ! find "${session_dir}/func" -maxdepth 1 -type f -name "*_bold.nii.gz" -print -quit 2>/dev/null | grep -q .; then
      echo "MISSING ${session_dir}/func/*_bold.nii.gz"
      failed=1
    fi
  done
done < <(rf1_read_subjects "$sublist")

if ((failed)); then
  echo "CHECK FAILED: BIDS/prepdata outputs incomplete for one or more of ${checked} expected session(s)."
else
  echo "CHECK PASSED: BIDS/prepdata outputs complete for ${checked} expected session(s)."
fi
exit "$failed"
