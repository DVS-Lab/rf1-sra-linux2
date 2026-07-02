#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash mriqc.sh [--dry-run] SUBJECT SESSION
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
    -*)
      usage
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

if (($# != 2)); then
  usage
  exit 2
fi

sub="$1"
ses="$2"
bidsdir="${PROJECT_ROOT}/bids"
outdir="${PROJECT_ROOT}/derivatives/mriqc"
scratch="${SCRATCH_ROOT}/$(whoami)"

if [[ ! -d "${bidsdir}/sub-${sub}/ses-${ses}" ]]; then
  echo "No BIDS data for optional sub-${sub} ses-${ses}; skipping MRIQC."
  exit 0
fi

export SINGULARITYENV_TEMPLATEFLOW_HOME=/opt/templateflow

cmd=(
  singularity run --cleanenv
  -B "${TEMPLATEFLOW_HOME}:/opt/templateflow"
  -B "${bidsdir}:/data"
  -B "${outdir}:/out"
  -B "${scratch}:/scratch"
  "$MRIQC_IMAGE"
  /data /out participant
  --participant_label "$sub"
  --session-id "$ses"
  --modalities bold
  --no-sub
  -w /scratch
)

printf 'MRIQC command:'
printf ' %q' "${cmd[@]}"
printf '\n'
if ((dry_run)); then
  echo "Dry run: not launching MRIQC."
  exit 0
fi

mkdir -p "$outdir" "$scratch"
rf1_require_file "$MRIQC_IMAGE"
"${cmd[@]}"
