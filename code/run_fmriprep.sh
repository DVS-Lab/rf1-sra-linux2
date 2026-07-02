#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash run_fmriprep.sh [--sublist FILE] [--jobs N] [--dry-run] [--overwrite]
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

sublist="$BATCH_SUBLIST"
max_jobs=2
dry_run=0
overwrite=0

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

if ! [[ "$max_jobs" =~ ^[1-9][0-9]*$ ]]; then
  echo "--jobs must be a positive integer, got: $max_jobs" >&2
  exit 2
fi

rf1_require_file "$sublist"
rf1_require_file "${SCRIPT_DIR}/fmriprep.sh"

if [[ -z "$FMRIPREP_NPROCS" ]]; then
  FMRIPREP_NPROCS=$((FMRIPREP_TOTAL_NPROCS / max_jobs))
  ((FMRIPREP_NPROCS < 1)) && FMRIPREP_NPROCS=1
fi
if [[ -z "$FMRIPREP_MEM_MB" ]]; then
  FMRIPREP_MEM_MB=$((FMRIPREP_TOTAL_MEM_MB / max_jobs))
  ((FMRIPREP_MEM_MB < 8000)) && FMRIPREP_MEM_MB=8000
fi
if ((FMRIPREP_OMP_NTHREADS > FMRIPREP_NPROCS)); then
  FMRIPREP_OMP_NTHREADS="$FMRIPREP_NPROCS"
fi
export FMRIPREP_NPROCS FMRIPREP_OMP_NTHREADS FMRIPREP_MEM_MB
echo "Using subject list: $sublist"
echo "fMRIPrep resource plan: up to ${max_jobs} subject job(s); each gets --nprocs ${FMRIPREP_NPROCS}, --omp-nthreads ${FMRIPREP_OMP_NTHREADS}, --mem ${FMRIPREP_MEM_MB} MB"

args=()
((dry_run)) && args+=(--dry-run)
((overwrite)) && args+=(--overwrite)

pids=()
while IFS= read -r sub; do
  rf1_wait_for_jobs "$max_jobs"
  echo "Launching fMRIPrep sub-${sub}"
  bash "${SCRIPT_DIR}/fmriprep.sh" "${args[@]}" "$sub" &
  pids+=("$!")
done < <(rf1_read_subjects "$sublist")

rf1_wait_all "${pids[@]}"
