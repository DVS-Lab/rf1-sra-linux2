#!/usr/bin/env bash

rf1_script_dir() {
  cd "$(dirname "${BASH_SOURCE[1]}")" >/dev/null 2>&1 && pwd
}

rf1_project_root() {
  local scriptdir
  scriptdir="$(rf1_script_dir)"
  printf '%s\n' "$(dirname "$scriptdir")"
}

rf1_load_config() {
  SCRIPT_DIR="$(rf1_script_dir)"
  PROJECT_ROOT="${PROJECT_ROOT:-$(dirname "$SCRIPT_DIR")}"
  if [[ -f "${SCRIPT_DIR}/config.env" ]]; then
    # shellcheck source=/dev/null
    source "${SCRIPT_DIR}/config.env"
  fi

  SOURCEDATA_ROOT="${SOURCEDATA_ROOT:-/ZPOOL/data/sourcedata/sourcedata/rf1-sra}"
  TOOLS_ROOT="${TOOLS_ROOT:-/ZPOOL/data/tools}"
  SCRATCH_ROOT="${SCRATCH_ROOT:-/ZPOOL/data/scratch}"
  TEMPLATEFLOW_HOME="${TEMPLATEFLOW_HOME:-${TOOLS_ROOT}/templateflow}"
  MPLCONFIGDIR_HOST="${MPLCONFIGDIR_HOST:-${TOOLS_ROOT}/mplconfigdir}"
  LICENSES_DIR="${LICENSES_DIR:-${TOOLS_ROOT}/licenses}"

  HEUDICONV_IMAGE="${HEUDICONV_IMAGE:-${TOOLS_ROOT}/heudiconv_1.3.3.sif}"
  MRIQC_IMAGE="${MRIQC_IMAGE:-${TOOLS_ROOT}/mriqc-24.0.2.simg}"
  FMRIPREP_IMAGE="${FMRIPREP_IMAGE:-${TOOLS_ROOT}/fmriprep-25.2.5.simg}"
  WARPKIT_IMAGE="${WARPKIT_IMAGE:-${TOOLS_ROOT}/warpkit.sif}"
}

rf1_usage() {
  printf 'Usage: %s\n' "$1" >&2
}

rf1_require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    printf 'Required file not found: %s\n' "$path" >&2
    return 1
  fi
}

rf1_require_dir() {
  local path="$1"
  if [[ ! -d "$path" ]]; then
    printf 'Required directory not found: %s\n' "$path" >&2
    return 1
  fi
}

rf1_read_subjects() {
  local sublist="$1"
  python3 "${SCRIPT_DIR}/print_subjects.py" "$sublist"
}

rf1_wait_for_jobs() {
  local max_jobs="$1"
  while (( "$(jobs -rp | wc -l | tr -d ' ')" >= max_jobs )); do
    sleep 2
  done
}

rf1_wait_all() {
  local failed=0
  local pid
  for pid in "$@"; do
    if ! wait "$pid"; then
      failed=1
    fi
  done
  return "$failed"
}
