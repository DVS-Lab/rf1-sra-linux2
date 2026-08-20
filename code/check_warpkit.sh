#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash check_warpkit.sh [--sublist FILE]
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
  for ses in 01 02; do
    session_dir="${PROJECT_ROOT}/bids/sub-${sub}/ses-${ses}"
    [[ -d "$session_dir" ]] || continue
    if [[ "$ses" == "01" ]]; then
      tasks=(ugr trust sharedreward doors socialdoors)
    else
      tasks=(ugr doors socialdoors)
    fi
    for task in "${tasks[@]}"; do
      runs=(1 2)
      [[ "$task" == "doors" || "$task" == "socialdoors" ]] && runs=(1)
      for run in "${runs[@]}"; do
        stem="sub-${sub}_ses-${ses}_task-${task}_run-${run}"
        indir="${session_dir}/func"
        if [[ ! -f "${indir}/${stem}_echo-1_part-mag_bold.nii.gz" ]]; then
          echo "SKIP sub-${sub} ses-${ses} task-${task} run-${run}: no BIDS echo-1 magnitude input"
          continue
        fi
        checked=$((checked + 1))
        reuse_source_run=""
        if reuse_spec="$(rf1_warpkit_reuse_spec "$sub" "$ses" "$task" "$run")"; then
          IFS=$'\t' read -r reuse_source_run reuse_reason <<< "$reuse_spec"
        fi
        if [[ -n "$reuse_source_run" ]]; then
          reuse_inputs_ok=1
          source_stem="sub-${sub}_ses-${ses}_task-${task}_run-${reuse_source_run}"
          for echo in 1 2 3 4; do
            [[ -f "${indir}/${stem}_echo-${echo}_part-mag_bold.nii.gz" ]] || reuse_inputs_ok=0
          done
          for input in \
            "${indir}/${stem}_echo-1_part-mag_bold.json" \
            "${PROJECT_ROOT}/derivatives/warpkit/sub-${sub}/ses-${ses}/${source_stem}.warpkit_done" \
            "${session_dir}/fmap/sub-${sub}_ses-${ses}_acq-${task}_run-${reuse_source_run}_fieldmap.nii.gz" \
            "${session_dir}/fmap/sub-${sub}_ses-${ses}_acq-${task}_run-${reuse_source_run}_fieldmap.json"
          do
            [[ -f "$input" ]] || reuse_inputs_ok=0
          done
          if ((reuse_inputs_ok == 0)); then
            echo "sub-${sub} ses-${ses} task-${task} run-${run}: incomplete reviewed Warpkit reuse inputs"
            failed=1
            continue
          fi
          echo "REUSE sub-${sub} ses-${ses} task-${task} run-${run}: source run-${reuse_source_run} (${reuse_reason})"
        elif ! python3 "${SCRIPT_DIR}/check_pipeline_state.py" warpkit-inputs "$indir" "$sub" "$ses" "$task" "$run"; then
          echo "sub-${sub} ses-${ses} task-${task} run-${run}: incomplete Warpkit inputs"
          failed=1
          continue
        fi

        outdir="${PROJECT_ROOT}/derivatives/warpkit/sub-${sub}/ses-${ses}"
        fmapdir="${session_dir}/fmap"
        expected=(
          "${outdir}/${stem}.warpkit_done"
          "${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap.nii.gz"
          "${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_magnitude.nii.gz"
          "${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap.json"
          "${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_magnitude.json"
        )
        if [[ -n "$reuse_source_run" ]]; then
          expected+=("${outdir}/${stem}_fieldmap-reuse.json")
        fi
        for output in "${expected[@]}"; do
          if [[ ! -f "$output" ]]; then
            echo "MISSING $output"
            failed=1
          fi
        done
      done
    done
  done
done < <(rf1_read_subjects "$sublist")

if ((failed)); then
  echo "CHECK FAILED: Warpkit outputs incomplete for one or more of ${checked} run(s)."
else
  echo "CHECK PASSED: Warpkit outputs complete for ${checked} run(s)."
fi
exit "$failed"
