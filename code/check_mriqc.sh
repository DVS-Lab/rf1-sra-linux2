#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash check_mriqc.sh [--sublist FILE]
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

sublist="${SCRIPT_DIR}/sublist_all.txt"
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
while IFS= read -r sub; do
  if [[ ! -d "${PROJECT_ROOT}/derivatives/mriqc/sub-${sub}" ]]; then
    echo "sub-${sub}: no MRIQC output folder"
    failed=1
  fi
done < <(rf1_read_subjects "$sublist")

exit "$failed"
