#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash run_tedana.sh [--sublist FILE] [--session 01|02] [--jobs N] [--dry-run] [--overwrite]
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
session=""

while (($#)); do
  case "$1" in
    --session)
      session="${2:-}"
      [[ "$session" == "01" || "$session" == "02" ]] || { usage; exit 2; }
      shift 2
      ;;
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

[[ "$max_jobs" =~ ^[1-9][0-9]*$ ]] || { usage; exit 2; }

rf1_require_file "$sublist"
rf1_require_file "${SCRIPT_DIR}/tedana.sh"
echo "Using subject list: $sublist"
echo "TEDANA job plan: up to ${max_jobs} subject job(s)"
echo "TEDANA executable: ${TEDANA_CMD}"

args=()
[[ -n "$session" ]] && args+=(--session "$session")
((dry_run)) && args+=(--dry-run)
((overwrite)) && args+=(--overwrite)

pids=()
while IFS= read -r sub; do
  rf1_wait_for_jobs "$max_jobs"
  echo "Launching TEDANA sub-${sub}"
  bash "${SCRIPT_DIR}/tedana.sh" "${args[@]}" "$sub" &
  pids+=("$!")
done < <(rf1_read_subjects "$sublist")

rf1_wait_all "${pids[@]}"
