#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash run_convert_behavior.sh [--sublist FILE] [--jobs N] [--sessions 01,02]
                                    [--tasks LIST] [--curation-file FILE]
                                    [--dry-run] [--overwrite]

Backfills canonical BIDS events without rerunning HeuDiConv. LIST is a
comma-separated subset of sharedreward,trust,ugr,socialdoors,doors.
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

sublist="$BATCH_SUBLIST"
max_jobs=4
sessions="01,02"
tasks="sharedreward,trust,ugr,socialdoors,doors"
dry_run=0
overwrite=0
curation_file="$BEHAVIOR_CURATION_FILE"

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
    --sessions)
      sessions="$2"
      shift 2
      ;;
    --tasks)
      tasks="$2"
      shift 2
      ;;
    --curation-file)
      curation_file="$2"
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
rf1_require_file "${SCRIPT_DIR}/convert_behavior.py"
rf1_require_file "$curation_file"
echo "Using subject list: $sublist"
echo "behavior conversion plan: up to ${max_jobs} subject/session job(s); sessions ${sessions}; tasks ${tasks}"

args=(--tasks "$tasks" --behavior-root "$BEHAVIOR_ROOT" --bids-root "${PROJECT_ROOT}/bids" --curation-file "$curation_file")
((dry_run)) && args+=(--dry-run)
((overwrite)) && args+=(--overwrite)

IFS=',' read -r -a session_values <<< "$sessions"
pids=()
while IFS= read -r sub; do
  for ses in "${session_values[@]}"; do
    rf1_wait_for_jobs "$max_jobs"
    echo "Launching behavior conversion sub-${sub} ses-${ses}"
    python3 "${SCRIPT_DIR}/convert_behavior.py" \
      --subject "$sub" --session "$ses" "${args[@]}" &
    pids+=("$!")
  done
done < <(rf1_read_subjects "$sublist")

rf1_wait_all "${pids[@]}"
