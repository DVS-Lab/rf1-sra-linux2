#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash prepdata.sh [--dry-run] [--overwrite] SUBJECT SESSION

Converts DICOMs to BIDS with HeuDiConv, defaces T1w data, shifts scans.tsv
dates, and stops. Run MRIQC separately with run_mriqc.sh.
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
    --)
      shift
      break
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
if [[ ! "$ses" =~ ^0[12]$ ]]; then
  echo "Session must be 01 or 02, got: $ses" >&2
  exit 2
fi

bidsroot="${PROJECT_ROOT}/bids"
scratch_user="${SCRATCH_ROOT}/$(whoami)"

cutoff="${SCANNER_UPGRADE_CUTOFF:-2025-03-04}"
cutoff_epoch="$(date -d "$cutoff" +%s)"

if [[ "$ses" == "02" ]]; then
  folder_sub="${sub}-2"
  dicom_template="/sourcedata/Smith-SRA-{subject}-2/Smith-SRA-{subject}-2/scans/*/*/DICOM/files/*.dcm"
  heuristic_name="heuristics_XA30.py"
  seen="XA30 heuristic, session 2"
else
  folder_sub="$sub"
  dicom_template="/sourcedata/Smith-SRA-{subject}/Smith-SRA-{subject}/scans/*/*/DICOM/files/*.dcm"
fi

subdir="${SOURCEDATA_ROOT}/Smith-SRA-${folder_sub}/Smith-SRA-${folder_sub}"
scandir="${subdir}/scans"
if [[ ! -d "$subdir" ]]; then
  if [[ "$ses" == "02" ]]; then
    echo "No source directory for optional sub-${sub} ses-${ses}; skipping."
    exit 0
  fi
  echo "Required source directory not found: $subdir" >&2
  exit 1
fi

if ! find "$scandir" -type f -name '*.dcm' -print -quit 2>/dev/null | grep -q .; then
  if [[ "$ses" == "02" ]]; then
    echo "No DICOMs for optional sub-${sub} ses-${ses}; skipping."
    exit 0
  fi
  echo "No DICOMs found under required scan directory: $scandir" >&2
  exit 1
fi

if [[ "$ses" == "01" ]]; then
  epoch="$(find "$scandir" -type f -name '*.dcm' -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | awk '{print int($1)}' || true)"
  [[ -z "${epoch:-}" ]] && epoch="$(stat -c %Y "$subdir" 2>/dev/null || echo 0)"
  if [[ "$sub" == "11433" || "$epoch" -le "$cutoff_epoch" ]]; then
    heuristic_name="heuristics_rf1.py"
  else
    heuristic_name="heuristics_XA30.py"
  fi
  seen="$(date -d "@$epoch" '+%Y-%m-%d %H:%M:%S')"
fi

heuristic_host="${scriptdir}/${heuristic_name}"
rf1_require_file "$heuristic_host"
echo "Heuristic chosen for sub-${sub} ses-${ses}: ${heuristic_name} [seen=${seen}; cutoff=${cutoff}]"

for localizer in "$scandir"/*-localizer; do
  [[ -d "$localizer" ]] || continue
  echo "Leaving raw localizer in place: $localizer"
done

target_session="${bidsroot}/sub-${sub}/ses-${ses}"
target_heudiconv="${bidsroot}/.heudiconv/${sub}/ses-${ses}"
if [[ -e "$target_session" && "$overwrite" -ne 1 ]]; then
  echo "Refusing to overwrite existing BIDS session without --overwrite: $target_session" >&2
  exit 1
fi

if ((dry_run)); then
  stage_root="${scratch_user}/prepdata-sub-${sub}-ses-${ses}.DRYRUN"
else
  mkdir -p "$bidsroot" "$scratch_user"
  stage_root="$(mktemp -d "${scratch_user}/prepdata-sub-${sub}-ses-${ses}.XXXXXX")"
  cleanup() {
    rm -rf "$stage_root"
  }
  trap cleanup EXIT
fi

cmd=(
  apptainer run --cleanenv
  -B "${PROJECT_ROOT}:/project"
  -B "${stage_root}:/out"
  -B "${SOURCEDATA_ROOT}:/sourcedata"
  "$HEUDICONV_IMAGE"
  -d "$dicom_template"
  -o /out/bids/
  -f "/project/code/${heuristic_name}"
  -s "$sub"
  -ss "$ses"
  -c dcm2niix
  -b --minmeta --overwrite
)

printf 'HeuDiConv command:'
printf ' %q' "${cmd[@]}"
printf '\n'
if ((dry_run)); then
  echo "Dry run: not converting, defacing, or shifting dates."
  exit 0
fi

rf1_require_file "$HEUDICONV_IMAGE"
"${cmd[@]}"

staged_session="${stage_root}/bids/sub-${sub}/ses-${ses}"
staged_heudiconv="${stage_root}/bids/.heudiconv/${sub}/ses-${ses}"
staged_dataset_description="${stage_root}/bids/dataset_description.json"
target_dataset_description="${bidsroot}/dataset_description.json"
rf1_require_dir "$staged_session"

if [[ ! -f "$target_dataset_description" ]]; then
  if [[ -f "$staged_dataset_description" ]]; then
    cp "$staged_dataset_description" "$target_dataset_description"
  else
    cat > "$target_dataset_description" <<'JSON'
{
  "Name": "RF1-SRA Linux2 fMRI",
  "BIDSVersion": "1.8.0",
  "DatasetType": "raw"
}
JSON
  fi
fi

if [[ -e "$target_session" ]]; then
  echo "Removing existing BIDS session immediately before installing staged output: $target_session"
  rf1_remove_tree_under "$bidsroot" "$target_session"
fi
mkdir -p "$(dirname "$target_session")"
mv "$staged_session" "$target_session"

if [[ -d "$staged_heudiconv" ]]; then
  if [[ -e "$target_heudiconv" ]]; then
    echo "Removing existing HeuDiConv metadata immediately before installing staged metadata: $target_heudiconv"
    rf1_remove_tree_under "${bidsroot}/.heudiconv" "$target_heudiconv"
  fi
  mkdir -p "$(dirname "$target_heudiconv")"
  mv "$staged_heudiconv" "$target_heudiconv"
fi

t1="${target_session}/anat/sub-${sub}_ses-${ses}_T1w.nii.gz"
if [[ -f "$t1" ]]; then
  echo "Defacing $t1"
  pydeface "$t1"
  def="${target_session}/anat/sub-${sub}_ses-${ses}_T1w_defaced.nii.gz"
  [[ -f "$def" ]] && mv -f "$def" "$t1"
fi

scans_tsv="${target_session}/sub-${sub}_ses-${ses}_scans.tsv"
[[ -f "$scans_tsv" ]] && python3 "${scriptdir}/shiftdates.py" "$scans_tsv"
