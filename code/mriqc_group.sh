#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash mriqc_group.sh [--dry-run]
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

dry_run=0
while (($#)); do
  case "$1" in
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

bidsdir="${PROJECT_ROOT}/bids"
outdir="${PROJECT_ROOT}/derivatives/mriqc"
scratch="${SCRATCH_ROOT}/$(whoami)/mriqc-group"

export SINGULARITYENV_TEMPLATEFLOW_HOME=/opt/templateflow

cmd=(
  singularity run --cleanenv
  -B "${TEMPLATEFLOW_HOME}:/opt/templateflow"
  -B "${bidsdir}:/data"
  -B "${outdir}:/out"
  -B "${scratch}:/scratch"
  "$MRIQC_IMAGE"
  /data /out group
  --modalities bold
  -w /scratch
)

printf 'MRIQC group command:'
printf ' %q' "${cmd[@]}"
printf '\n'
if ((dry_run)); then
  echo "Dry run: not launching MRIQC group report."
  exit 0
fi

rf1_require_dir "$bidsdir"
rf1_require_dir "$outdir"
rf1_require_file "$MRIQC_IMAGE"
mkdir -p "$outdir" "$scratch"
"${cmd[@]}"
