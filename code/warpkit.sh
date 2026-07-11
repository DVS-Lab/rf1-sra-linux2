#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash warpkit.sh [--dry-run] [--overwrite] SUBJECT SESSION TASK RUN
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

dry_run=0
overwrite=0
while (($#)); do
  case "$1" in
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
    -*)
      usage
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

if (($# != 4)); then
  usage
  exit 2
fi

sub="$1"
ses="$2"
task="$3"
run="$4"
stem="sub-${sub}_ses-${ses}_task-${task}_run-${run}"
warpkit_backend="${WARPKIT_BACKEND:-apptainer}"
warpkit_cmd_name="${WARPKIT_CMD:-wk-medic}"
warpkit_n_cpus="${WARPKIT_N_CPUS:-1}"

logdir="${PROJECT_ROOT}/logs"
mkdir -p "$logdir"

if [[ "$ses" == "02" && ! -d "${PROJECT_ROOT}/bids/sub-${sub}/ses-02" ]]; then
  echo "No optional ses-02 BIDS directory for sub-${sub}; skipping."
  exit 0
fi

indir="${PROJECT_ROOT}/bids/sub-${sub}/ses-${ses}/func"
if [[ ! -d "$indir" ]]; then
  echo "No func directory for sub-${sub} ses-${ses}; skipping warpkit for ${task} run-${run}."
  exit 0
fi

if ! python3 "${scriptdir}/check_pipeline_state.py" warpkit-inputs "$indir" "$sub" "$ses" "$task" "$run"; then
  echo "Missing Warpkit input(s) for sub-${sub} ses-${ses} task-${task} run-${run}" \
    >> "${logdir}/missingFiles-warpkit.log"
  exit 0
fi

outdir="${PROJECT_ROOT}/derivatives/warpkit/sub-${sub}/ses-${ses}"
fmapdir="${PROJECT_ROOT}/bids/sub-${sub}/ses-${ses}/fmap"
doneflag="${outdir}/${stem}.warpkit_done"
fmap_out="${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap.nii.gz"
mag_out="${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_magnitude.nii.gz"
fmap_json="${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap.json"
mag_json="${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_magnitude.json"

if [[ -e "$doneflag" && -e "$fmap_out" && "$overwrite" -ne 1 ]]; then
  echo "EXISTS (skipping): warpkit complete for sub-${sub} ses-${ses} ${task} run-${run}"
  exit 0
fi

if [[ -e "$fmap_out" && "$overwrite" -ne 1 ]]; then
  echo "Refusing to overwrite existing fieldmap without --overwrite: $fmap_out" >&2
  exit 1
fi

mkdir -p "$outdir" "$fmapdir"

cleanup_default_gre=(
  "${fmapdir}/sub-${sub}_ses-${ses}_acq-bold_magnitude.nii.gz"
  "${fmapdir}/sub-${sub}_ses-${ses}_acq-bold_magnitude.json"
  "${fmapdir}/sub-${sub}_ses-${ses}_acq-bold_phasediff.nii.gz"
  "${fmapdir}/sub-${sub}_ses-${ses}_acq-bold_phasediff.json"
)

export APPTAINERENV_OMP_NUM_THREADS="${APPTAINERENV_OMP_NUM_THREADS:-1}"
export APPTAINERENV_OPENBLAS_NUM_THREADS="${APPTAINERENV_OPENBLAS_NUM_THREADS:-1}"
export APPTAINERENV_NUMEXPR_NUM_THREADS="${APPTAINERENV_NUMEXPR_NUM_THREADS:-1}"
export APPTAINERENV_MKL_NUM_THREADS="${APPTAINERENV_MKL_NUM_THREADS:-1}"
export APPTAINERENV_JULIA_NUM_THREADS="${APPTAINERENV_JULIA_NUM_THREADS:-1}"
export APPTAINERENV_JULIA_NUM_GC_THREADS="${APPTAINERENV_JULIA_NUM_GC_THREADS:-1}"

magnitude_paths=()
phase_paths=()
metadata_paths=()
for echo in 1 2 3 4; do
  magnitude_paths+=("${indir}/${stem}_echo-${echo}_part-mag_bold.nii.gz")
  phase_paths+=("${indir}/${stem}_echo-${echo}_part-phase_bold.nii.gz")
  metadata_paths+=("${indir}/${stem}_echo-${echo}_part-phase_bold.json")
done

warpkit_cmd=()
case "$warpkit_backend" in
  apptainer)
    container_magnitude_paths=()
    container_phase_paths=()
    container_metadata_paths=()
    for echo in 1 2 3 4; do
      container_magnitude_paths+=("/base/${stem}_echo-${echo}_part-mag_bold.nii.gz")
      container_phase_paths+=("/base/${stem}_echo-${echo}_part-phase_bold.nii.gz")
      container_metadata_paths+=("/base/${stem}_echo-${echo}_part-phase_bold.json")
    done
    warpkit_cmd=(
      apptainer run --cleanenv
      -B "$indir:/base"
      -B "$outdir:/out"
      "$WARPKIT_IMAGE"
      --n_cpus "$warpkit_n_cpus"
      --magnitude "${container_magnitude_paths[@]}"
      --phase "${container_phase_paths[@]}"
      --metadata "${container_metadata_paths[@]}"
      --out_prefix "/out/${stem}"
    )
    ;;
  native)
    warpkit_cmd=(
      "$warpkit_cmd_name"
      --n-cpus "$warpkit_n_cpus"
      --magnitude "${magnitude_paths[@]}"
      --phase "${phase_paths[@]}"
      --metadata "${metadata_paths[@]}"
      --out-prefix "${outdir}/${stem}"
    )
    ;;
  *)
    echo "Unsupported WARPKIT_BACKEND: $warpkit_backend (expected apptainer or native)" >&2
    exit 2
    ;;
esac

printf 'Warpkit command:'
printf ' %q' "${warpkit_cmd[@]}"
printf '\n'
echo "Warpkit thread plan: backend=${warpkit_backend}; command=${warpkit_cmd_name}; WarpKit n_cpus=${warpkit_n_cpus}; OMP=${APPTAINERENV_OMP_NUM_THREADS}; OpenBLAS=${APPTAINERENV_OPENBLAS_NUM_THREADS}; NumExpr=${APPTAINERENV_NUMEXPR_NUM_THREADS}; MKL=${APPTAINERENV_MKL_NUM_THREADS}; Julia=${APPTAINERENV_JULIA_NUM_THREADS}; Julia GC=${APPTAINERENV_JULIA_NUM_GC_THREADS}"
if ((dry_run)); then
  echo "Dry run: not running Warpkit or writing fmap outputs."
  exit 0
fi

case "$warpkit_backend" in
  apptainer)
    rf1_require_file "$WARPKIT_IMAGE"
    command -v apptainer >/dev/null 2>&1 || { echo "Required command not found: apptainer" >&2; exit 1; }
    ;;
  native)
    command -v "$warpkit_cmd_name" >/dev/null 2>&1 || { echo "Required command not found: $warpkit_cmd_name" >&2; exit 1; }
    ;;
esac
command -v fslroi >/dev/null 2>&1 || { echo "Required command not found: fslroi" >&2; exit 1; }

if ((overwrite)); then
  for old in "${cleanup_default_gre[@]}" "$fmap_out" "$mag_out" "$fmap_json" "$mag_json"; do
    [[ -e "$old" ]] || continue
    python3 "${scriptdir}/check_pipeline_state.py" safe-child "$fmapdir" "$old" >/dev/null
    echo "Removing prior generated output: $old"
    rm -f "$old"
  done
  if [[ -e "$doneflag" ]]; then
    python3 "${scriptdir}/check_pipeline_state.py" safe-child "$outdir" "$doneflag" >/dev/null
    echo "Removing prior completion marker: $doneflag"
    rm -f "$doneflag"
  fi
fi

"${warpkit_cmd[@]}"

fieldmaps_4d="${outdir}/${stem}_fieldmaps.nii"
rf1_require_file "$fieldmaps_4d"

fslroi "$fieldmaps_4d" "${fmap_out%.nii.gz}" 0 1
fslroi \
  "${indir}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.nii.gz" \
  "${mag_out%.nii.gz}" \
  0 1

cp \
  "${indir}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json" \
  "$mag_json"
cp \
  "${indir}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-phase_bold.json" \
  "$fmap_json"

for output in "$fmap_out" "$mag_out" "$fmap_json" "$mag_json"; do
  rf1_require_file "$output"
done
touch "$doneflag"
