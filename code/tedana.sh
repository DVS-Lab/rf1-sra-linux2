#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash tedana.sh [--dry-run] [--overwrite] SUBJECT
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

dry_run=0
overwrite=0
while (($#)); do
  case "$1" in
    --dry-run)
      dry_run=1
      shift
      ;;
    --overwrite)
      overwrite=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      usage
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

if (($# != 1)); then
  usage
  exit 2
fi

sub="$1"
bidsdir="${PROJECT_ROOT}/bids"
derivativesdir="${PROJECT_ROOT}/derivatives"
logdir="${PROJECT_ROOT}/logs"
missinglog="${logdir}/missing-tedanaInput.log"
logfile="${logdir}/tedana_output.log"
mkdir -p "$logdir"

get_echo_time() {
  python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())
echo_time = data.get("EchoTime")
if echo_time is None:
    raise SystemExit(f"EchoTime missing from {path}")
print(echo_time)
PY
}

failures=0
for ses in 01 02; do
  [[ -d "${bidsdir}/sub-${sub}/ses-${ses}" ]] || continue
  if [[ "$ses" == "01" ]]; then
    tasks=(socialdoors doors trust sharedreward ugr)
  else
    tasks=(socialdoors doors ugr)
  fi

  for task in "${tasks[@]}"; do
    runs=(1 2)
    [[ "$task" == "doors" || "$task" == "socialdoors" ]] && runs=(1)
    for run in "${runs[@]}"; do
      if [[ "$overwrite" -ne 1 ]] && python3 "${scriptdir}/check_pipeline_state.py" tedana-complete "$derivativesdir" "$sub" "$ses" "$task" "$run" >/dev/null; then
        echo "EXISTS (skipping): TEDANA sub-${sub} ses-${ses} task-${task} run-${run}"
        continue
      fi

      indata="${derivativesdir}/fmriprep/sub-${sub}/ses-${ses}/func"
      bidsfuncdir="${bidsdir}/sub-${sub}/ses-${ses}/func"
      outdir="${derivativesdir}/tedana/sub-${sub}/ses-${ses}"
      mkdir -p "$outdir"

      echoes=()
      echo_times=()
      missing=0
      for echo in 1 2 3 4; do
        echo_file="${indata}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-${echo}_part-mag_desc-preproc_bold.nii.gz"
        json_file="${bidsfuncdir}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-${echo}_part-mag_bold.json"
        if [[ ! -f "$echo_file" || ! -f "$json_file" ]]; then
          echo "Missing TEDANA input for sub-${sub} ses-${ses} task-${task} run-${run} echo-${echo}" >> "$missinglog"
          missing=1
          break
        fi
        echoes+=("$echo_file")
        echo_times+=("$(get_echo_time "$json_file")")
      done
      ((missing)) && continue

      cmd=(
        tedana
        -d "${echoes[@]}"
        -e "${echo_times[@]}"
        --out-dir "$outdir"
        --prefix "sub-${sub}_ses-${ses}_task-${task}_run-${run}"
        --convention bids
        --fittype curvefit
      )
      ((overwrite)) && cmd+=(--overwrite)

      printf 'TEDANA command:'
      printf ' %q' "${cmd[@]}"
      printf '\n'
      if ((dry_run)); then
        continue
      fi

      if ! "${cmd[@]}" >> "$logfile" 2>&1; then
        echo "TEDANA failed for sub-${sub} ses-${ses} task-${task} run-${run}" >&2
        failures=1
        continue
      fi
      if ! python3 "${scriptdir}/check_pipeline_state.py" tedana-complete "$derivativesdir" "$sub" "$ses" "$task" "$run"; then
        failures=1
      fi
    done
  done
done

exit "$failures"
