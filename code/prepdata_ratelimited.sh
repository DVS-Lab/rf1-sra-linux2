#!/usr/bin/env bash
set -euo pipefail

# Rate-limited version to prevent I/O issues with many subjects in parallel from ZPOOL
# Lock file serializes the sourcedata searches

sub=$1
ses=$2

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
dsroot="$(dirname "$scriptdir")"
sourcedata=/ZPOOL/data/sourcedata/sourcedata/rf1-sra

# Lock file to serialize sourcedata access during initial scan
SCAN_LOCK="$dsroot/.sourcedata_scan.lock"
LOCK_TIMEOUT=300  # 5 minutes max wait

# Function to acquire lock with timeout
acquire_scan_lock() {
  local waited=0
  while [ $waited -lt $LOCK_TIMEOUT ]; do
    if mkdir "$SCAN_LOCK" 2>/dev/null; then
      trap "rmdir '$SCAN_LOCK' 2>/dev/null || true" EXIT
      return 0
    fi
    echo "[sub-${sub} ses-${ses}] Waiting for sourcedata scan lock... (${waited}s)"
    sleep 5
    waited=$((waited + 5))
  done
  echo "[sub-${sub} ses-${ses}] ERROR: Could not acquire scan lock after ${LOCK_TIMEOUT}s" >&2
  return 1
}

# Acquire lock before doing ANY sourcedata operations
acquire_scan_lock

cutoff_epoch=$(date -d '2025-03-18' +%s)

# Session-specific logic (protected by lock)
if [ "$ses" = "02" ]; then
  folder_sub="${sub}-2"
  heuristics_file="/out/code/heuristics_XA30.py"
  dicom_template="/sourcedata/Smith-SRA-{subject}-2/Smith-SRA-{subject}-2/scans/*/*/DICOM/files/*.dcm"

  subdir="$sourcedata/Smith-SRA-${folder_sub}/Smith-SRA-${folder_sub}"
  scandir="$subdir/scans"
  
  # Quick existence check using find with -quit (stops after first match)
  if ! find "$scandir" -type f -name '*.dcm' -print -quit 2>/dev/null | grep -q .; then
    seen="N/A"
    echo "No ses-02 for sub-${sub} (seen=${seen}). Skipping ses-${ses}."
    rmdir "$SCAN_LOCK" 2>/dev/null || true
    trap - EXIT
    exit 0
  fi

  # Find newest DICOM (limit to 100 files for speed)
  epoch=$(find "$scandir" -type f -name '*.dcm' -printf '%T@ %p\n' 2>/dev/null | head -100 | sort -n | tail -1 | awk '{print int($1)}' || true)
  [ -z "${epoch:-}" ] && epoch=$(stat -c %Y "$subdir" 2>/dev/null || echo 0)
  seen="$(date -d "@$epoch" '+%Y-%m-%d %H:%M:%S')"
else
  folder_sub="${sub}"
  dicom_template="/sourcedata/Smith-SRA-{subject}/Smith-SRA-{subject}/scans/*/*/DICOM/files/*.dcm"

  subdir="$sourcedata/Smith-SRA-${folder_sub}/Smith-SRA-${folder_sub}"
  scandir="$subdir/scans"
  
  # Limit find to 100 files for speed
  epoch=$(find "$scandir" -type f -name '*.dcm' -printf '%T@ %p\n' 2>/dev/null | head -100 | sort -n | tail -1 | awk '{print int($1)}' || true)
  [ -z "${epoch:-}" ] && epoch=$(stat -c %Y "$subdir" 2>/dev/null || echo 0)

  if [ "$epoch" -le "$cutoff_epoch" ]; then
    heuristics_file="/out/code/heuristics_rf1.py"
  else
    heuristics_file="/out/code/heuristics_XA30.py"
  fi
  seen="$(date -d "@$epoch" '+%Y-%m-%d %H:%M:%S')"
fi

echo "Heuristic chosen for sub-${sub} ses-${ses}: $(basename "$heuristics_file") [seen=${seen}]"

# Localizer handling (still under lock)
locdir=$sourcedata/localizers/Smith-SRA-$folder_sub
if [ ! -d "$locdir" ]; then
  mkdir -p "$locdir"
fi

for localizers in "$scandir"/*-localizer; do
  [ -d "$localizers" ] || continue
  echo "Moving $localizers to $locdir"
  mv "$localizers" "$locdir/"
done

# Release lock BEFORE running heudiconv (heudiconv can run in parallel)
rmdir "$SCAN_LOCK" 2>/dev/null || true
trap - EXIT

echo "[sub-${sub} ses-${ses}] Sourcedata scan complete, starting heudiconv..."

# PART 1: Running heudiconv
mkdir -p "$dsroot/bids"
rm -rf "$dsroot/bids/sub-${sub}/ses-${ses}"
rm -rf "$dsroot/bids/.heudiconv/${sub}/ses-${ses}"

apptainer run --cleanenv \
  -B "$dsroot:/out" \
  -B "$sourcedata:/sourcedata" \
  /ZPOOL/data/tools/heudiconv_1.3.3.sif \
  -d "$dicom_template" \
  -o /out/bids/ \
  -f "$heuristics_file" \
  -s "$sub" \
  -ss "$ses" \
  -c dcm2niix \
  -b --minmeta --overwrite

# PART 2: Defacing with pydeface
bidsroot="$dsroot/bids"
echo "Defacing subject $sub session $ses"

t1="$bidsroot/sub-${sub}/ses-${ses}/anat/sub-${sub}_ses-${ses}_T1w.nii.gz"
if [ -f "$t1" ]; then
  pydeface "$t1"
  def="$bidsroot/sub-${sub}/ses-${ses}/anat/sub-${sub}_ses-${ses}_T1w_defaced.nii.gz"
  [ -f "$def" ] && mv -f "$def" "$t1"
fi

scans_tsv="$bidsroot/sub-${sub}/ses-${ses}/sub-${sub}_ses-${ses}_scans.tsv"
[ -f "$scans_tsv" ] && python "$scriptdir/shiftdates.py" "$scans_tsv" || true

echo "[sub-${sub} ses-${ses}] prepdata.sh complete"