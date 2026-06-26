#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash run_mriqc.sh [--sublist FILE] [--jobs N] [--dry-run]
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

sublist="${SCRIPT_DIR}/sublist_all.txt"
max_jobs=10
dry_run=0

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
rf1_require_file "${SCRIPT_DIR}/mriqc.sh"

args=()
((dry_run)) && args+=(--dry-run)

pids=()
while IFS= read -r sub; do
  for ses in 01 02; do
    rf1_wait_for_jobs "$max_jobs"
    echo "Launching MRIQC sub-${sub} ses-${ses}"
    bash "${SCRIPT_DIR}/mriqc.sh" "${args[@]}" "$sub" "$ses" &
    pids+=("$!")
  done
done < <(rf1_read_subjects "$sublist")

rf1_wait_all "${pids[@]}"
