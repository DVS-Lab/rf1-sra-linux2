#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash check_mriqc.sh [--sublist FILE]
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
failed=0
checked=0
while IFS= read -r sub; do
  subject_dir="${PROJECT_ROOT}/bids/sub-${sub}"
  if [[ ! -d "$subject_dir" ]]; then
    echo "sub-${sub}: no BIDS subject folder; run prepdata before MRIQC"
    failed=1
    continue
  fi
  for session_dir in "$subject_dir"/ses-*; do
    [[ -d "$session_dir" ]] || continue
    ses="${session_dir##*/}"
    input_count=0
    while IFS= read -r bold; do
      input_count=$((input_count + 1))
      checked=$((checked + 1))
      rel="${bold#$subject_dir/}"
      expected="${PROJECT_ROOT}/derivatives/mriqc/sub-${sub}/${rel%.nii.gz}.json"
      if [[ ! -f "$expected" ]]; then
        echo "MISSING $expected"
        failed=1
      fi
    done < <(find "${session_dir}/func" -maxdepth 1 -type f -name "*_echo-2_part-mag_bold.nii.gz" 2>/dev/null | sort)
    if ((input_count == 0)); then
      echo "sub-${sub} ${ses}: no echo-2 magnitude BOLD inputs found for MRIQC"
      failed=1
    fi
  done
done < <(rf1_read_subjects "$sublist")

if ((failed)); then
  echo "CHECK FAILED: MRIQC outputs incomplete for one or more of ${checked} BOLD input(s)."
else
  echo "CHECK PASSED: MRIQC outputs complete for ${checked} BOLD input(s)."
fi
exit "$failed"
