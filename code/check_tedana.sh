#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash check_tedana.sh [--sublist FILE] [--session 01|02] [--expected-runs N]
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

sublist="$BATCH_SUBLIST"
sessions=(01 02)
expected_runs=""
while (($#)); do
  case "$1" in
    --session)
      [[ "${2:-}" == "01" || "${2:-}" == "02" ]] || { usage; exit 2; }
      sessions=("$2")
      shift 2
      ;;
    --expected-runs)
      expected_runs="${2:-}"
      [[ "$expected_runs" =~ ^[1-9][0-9]*$ ]] || { usage; exit 2; }
      shift 2
      ;;
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
  for ses in "${sessions[@]}"; do
    [[ -d "${PROJECT_ROOT}/bids/sub-${sub}/ses-${ses}" ]] || continue
    if [[ "$ses" == "01" ]]; then
      tasks=(socialdoors doors trust sharedreward ugr)
    else
      tasks=(socialdoors doors ugr)
    fi
    for task in "${tasks[@]}"; do
      runs=(1 2)
      [[ "$task" == "doors" || "$task" == "socialdoors" ]] && runs=(1)
      for run in "${runs[@]}"; do
        stem="sub-${sub}_ses-${ses}_task-${task}_run-${run}"
        bids_input="${PROJECT_ROOT}/bids/sub-${sub}/ses-${ses}/func/${stem}_echo-1_part-mag_bold.nii.gz"
        if [[ ! -f "$bids_input" ]]; then
          echo "SKIP sub-${sub} ses-${ses} task-${task} run-${run}: no BIDS echo-1 magnitude input"
          continue
        fi
        checked=$((checked + 1))
        if ! python3 "${SCRIPT_DIR}/check_pipeline_state.py" tedana-complete "${PROJECT_ROOT}/derivatives" "$sub" "$ses" "$task" "$run"; then
          echo "sub-${sub} ses-${ses} task-${task} run-${run}: incomplete TEDANA outputs"
          failed=1
        fi
      done
    done
  done
done < <(rf1_read_subjects "$sublist")

if ((checked == 0)) || { [[ -n "$expected_runs" ]] && ((checked != expected_runs)); }; then
  echo "CHECK FAILED: found ${checked} acquired run(s); expected ${expected_runs:-at least one}."
  failed=1
fi

if ((failed)); then
  echo "CHECK FAILED: TEDANA outputs incomplete for one or more of ${checked} run(s)."
else
  echo "CHECK PASSED: TEDANA outputs complete for ${checked} run(s)."
fi
exit "$failed"
