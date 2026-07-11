#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash run_warpkit.sh [--sublist FILE] [--jobs N] [--dry-run] [--overwrite]
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

sublist="$BATCH_SUBLIST"
max_jobs=8
dry_run=0
overwrite=0
omp_threads="${OMP_THREADS:-4}"
julia_threads="${JULIA_NUM_THREADS:-1}"
julia_gc_threads="${JULIA_NUM_GC_THREADS:-1}"
warpkit_n_cpus="${WARPKIT_N_CPUS:-1}"

while (($#)); do
  case "$1" in
    --sublist)
      sublist="$2"
      shift 2
      ;;
    --jobs)
      max_jobs="$2"
      shift 2
      ;;
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
    *)
      usage
      exit 2
      ;;
  esac
done

rf1_require_file "$sublist"
rf1_require_file "${SCRIPT_DIR}/warpkit.sh"
echo "Using subject list: $sublist"
echo "Warpkit job plan: up to ${max_jobs} subject/session/task/run job(s); WarpKit n_cpus ${warpkit_n_cpus}; OMP threads per job ${omp_threads}; Julia threads ${julia_threads}; Julia GC threads ${julia_gc_threads}"

args=()
((dry_run)) && args+=(--dry-run)
((overwrite)) && args+=(--overwrite)

pids=()
while IFS= read -r sub; do
  for ses in 01 02; do
    if [[ "$ses" == "01" ]]; then
      tasks=(ugr trust sharedreward doors socialdoors)
    else
      tasks=(ugr doors socialdoors)
    fi
    for task in "${tasks[@]}"; do
      runs=(1 2)
      [[ "$task" == "doors" || "$task" == "socialdoors" ]] && runs=(1)
      for run in "${runs[@]}"; do
        rf1_wait_for_jobs "$max_jobs"
        echo "Launching warpkit sub-${sub} ses-${ses} task-${task} run-${run}"
        APPTAINERENV_OMP_NUM_THREADS="$omp_threads" \
        APPTAINERENV_OPENBLAS_NUM_THREADS=1 \
        APPTAINERENV_NUMEXPR_NUM_THREADS=1 \
        APPTAINERENV_MKL_NUM_THREADS=1 \
        APPTAINERENV_JULIA_NUM_THREADS="$julia_threads" \
        APPTAINERENV_JULIA_NUM_GC_THREADS="$julia_gc_threads" \
        WARPKIT_N_CPUS="$warpkit_n_cpus" \
          bash "${SCRIPT_DIR}/warpkit.sh" "${args[@]}" "$sub" "$ses" "$task" "$run" &
        pids+=("$!")
      done
    done
  done
done < <(rf1_read_subjects "$sublist")

rf1_wait_all "${pids[@]}"
