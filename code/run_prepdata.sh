#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash run_prepdata.sh [--sublist FILE] [--jobs N] [--dry-run] [--overwrite]

Runs prepdata.sh for every subject in the subject list and sessions 01/02.
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

sublist="$BATCH_SUBLIST"
max_jobs=6
dry_run=0
overwrite=0
omp_threads="${OMP_THREADS:-12}"

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
rf1_require_file "${SCRIPT_DIR}/prepdata.sh"

args=()
((dry_run)) && args+=(--dry-run)
((overwrite)) && args+=(--overwrite)

pids=()
while IFS= read -r sub; do
  for ses in 01 02; do
    rf1_wait_for_jobs "$max_jobs"
    echo "Launching prepdata sub-${sub} ses-${ses}"
    APPTAINERENV_OMP_NUM_THREADS="$omp_threads" \
    APPTAINERENV_OPENBLAS_NUM_THREADS=1 \
    APPTAINERENV_NUMEXPR_NUM_THREADS=1 \
    APPTAINERENV_MKL_NUM_THREADS=1 \
      bash "${SCRIPT_DIR}/prepdata.sh" "${args[@]}" "$sub" "$ses" &
    pids+=("$!")
  done
done < <(rf1_read_subjects "$sublist")

rf1_wait_all "${pids[@]}"
