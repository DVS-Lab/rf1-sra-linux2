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
  PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
  SOURCEDATA_ROOT="/ZPOOL/data/sourcedata/sourcedata/rf1-sra"
  SOURCEDATA_EXCLUSIONS_ROOT="${SOURCEDATA_EXCLUSIONS_ROOT:-/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions}"
  BEHAVIOR_ROOT="${BEHAVIOR_ROOT:-/ZPOOL/data/projects/rf1-sra/stimuli}"
  BEHAVIOR_CURATION_FILE="${BEHAVIOR_CURATION_FILE:-${SCRIPT_DIR}/behavior_curation.tsv}"
  SUPPLEMENTAL_SOURCES_FILE="${SUPPLEMENTAL_SOURCES_FILE:-${SCRIPT_DIR}/supplemental_sources.tsv}"
  TOOLS_ROOT="/ZPOOL/data/tools"
  SCRATCH_ROOT="/ZPOOL/data/scratch"
  TEMPLATEFLOW_HOME="${TOOLS_ROOT}/templateflow"
  MPLCONFIGDIR_HOST="${TOOLS_ROOT}/mplconfigdir"
  LICENSES_DIR="${TOOLS_ROOT}/licenses"

  HEUDICONV_IMAGE="${TOOLS_ROOT}/heudiconv-1.4.0.sif"
  PYDEFACE_CMD="${PYDEFACE_CMD:-${TOOLS_ROOT}/anaconda/tug87422/envs/pydeface-2.1/bin/pydeface}"
  MRIQC_IMAGE="${TOOLS_ROOT}/mriqc-24.0.2.simg"
  MRIQC_NPROCS="${MRIQC_NPROCS:-8}"
  MRIQC_OMP_NTHREADS="${MRIQC_OMP_NTHREADS:-4}"
  MRIQC_MEM_GB="${MRIQC_MEM_GB:-20}"
  FMRIPREP_IMAGE="${TOOLS_ROOT}/fmriprep-25.2.5.simg"
  WARPKIT_IMAGE="${TOOLS_ROOT}/warpkit.sif"
  WARPKIT_BACKEND="${WARPKIT_BACKEND:-native}"
  WARPKIT_CMD="${WARPKIT_CMD:-${TOOLS_ROOT}/anaconda/tug87422/envs/warpkit-1.4.0/bin/wk-medic}"
  WARPKIT_REUSE_FILE="${WARPKIT_REUSE_FILE:-${SCRIPT_DIR}/warpkit_reuse.tsv}"
  TEDANA_CMD="${TEDANA_CMD:-${TOOLS_ROOT}/anaconda/tug87422/envs/tedana-26.0.3/bin/tedana}"
  FMRIPREP_OUTPUT_SPACES="MNI152NLin6Asym fsLR"
  FMRIPREP_CIFTI_DENSITY="91k"
  FMRIPREP_TOTAL_NPROCS="${FMRIPREP_TOTAL_NPROCS:-96}"
  FMRIPREP_TOTAL_MEM_MB="${FMRIPREP_TOTAL_MEM_MB:-196000}"
  FMRIPREP_OMP_NTHREADS="${FMRIPREP_OMP_NTHREADS:-8}"
  FMRIPREP_NPROCS="${FMRIPREP_NPROCS:-}"
  FMRIPREP_MEM_MB="${FMRIPREP_MEM_MB:-}"
  BATCH_SUBLIST="${SCRIPT_DIR}/sublist-new.txt"
}

rf1_warpkit_reuse_spec() {
  local subject="$1"
  local ses="$2"
  local task="$3"
  local run="$4"
  local reuse_file="${WARPKIT_REUSE_FILE:-${SCRIPT_DIR}/warpkit_reuse.tsv}"

  [[ -f "$reuse_file" ]] || return 1
  awk -F '\t' \
    -v subject="$subject" -v ses="$ses" -v task="$task" -v run="$run" '
      NR > 1 && $1 == subject && $2 == ses && $3 == task && $4 == run {
        print $5 "\t" $6
        found = 1
        exit
      }
      END { if (!found) exit 1 }
    ' "$reuse_file"
}

rf1_remove_tree_under() {
  local root="$1"
  local target="$2"
  local root_real target_real
  root_real="$(realpath -m "$root")"
  target_real="$(realpath -m "$target")"

  if [[ "$target_real" == "$root_real" || "$target_real" != "$root_real"/* || ${#target_real} -lt 20 ]]; then
    printf 'Refusing unsafe removal outside %s: %s\n' "$root_real" "$target_real" >&2
    return 1
  fi

  rm -rf -- "$target_real"
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
  local sub excluded_source

  while IFS= read -r sub; do
    excluded_source="${SOURCEDATA_EXCLUSIONS_ROOT}/Smith-SRA-${sub}"
    if [[ "${RF1_INCLUDE_SOURCE_EXCLUDED:-0}" != "1" && -d "$excluded_source" ]]; then
      printf 'SKIP source-excluded sub-%s: %s\n' "$sub" "$excluded_source" >&2
      continue
    fi
    printf '%s\n' "$sub"
  done < <(python3 "${SCRIPT_DIR}/print_subjects.py" "$sublist")
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
