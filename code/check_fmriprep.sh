#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash check_fmriprep.sh [--sublist FILE]
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
mapfile -t subjects < <(rf1_read_subjects "$sublist")
printf 'Checking fMRIPrep outputs under: %s\n' "${PROJECT_ROOT}/derivatives/fmriprep" >&2
printf 'Using subject list: %s\n' "$sublist" >&2
printf 'Checking %d subject(s).\n' "${#subjects[@]}" >&2
failed=0
checked=0
for sub in "${subjects[@]}"; do
  checked=$((checked + 1))
  if [[ ! -e "${PROJECT_ROOT}/derivatives/fmriprep/sub-${sub}" && ! -e "${PROJECT_ROOT}/derivatives/fmriprep/sub-${sub}.html" ]]; then
    printf 'sub-%s: no fMRIPrep subject outputs found in this checkout; confirm this subject was run here.\n' "$sub" >&2
  fi
  if ! python3 "${SCRIPT_DIR}/check_pipeline_state.py" fmriprep-complete "${PROJECT_ROOT}/bids" "${PROJECT_ROOT}/derivatives" "$sub"; then
    echo "sub-${sub}: incomplete fMRIPrep outputs"
    failed=1
  fi
done

if ((failed)); then
  echo "CHECK FAILED: fMRIPrep outputs incomplete for one or more of ${checked} subject(s)."
else
  echo "CHECK PASSED: fMRIPrep outputs complete for ${checked} subject(s)."
fi
exit "$failed"
