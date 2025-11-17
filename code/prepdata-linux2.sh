#!/usr/bin/env bash
set -euo pipefail

# This code will convert DICOMS to BIDS (PART 1). Will also deface (PART 2) and run MRIQC (PART 3).
#
# usage:  bash prepdata.sh sub ses
# example: bash prepdata.sh 10418 01
#
# Notes:
# 1) Containers live under /ZPOOL/data/tools on this machine. YODA principles suggest sharing these paths if possible.
# 2) Other projects should use Jeff's Python for fixing IntendedFor (this pipeline uses a separate step elsewhere).
# 3) Aside from containers, the only absolute path here is to raw sourcedata.
# 4) Heuristic selection:
#       - ses-02: ALWAYS heuristics_XA30.py (all ses-02 scans are XA30-era)
#       - ses-01: If newest DICOM mtime is <= March 18, 2025, then heuristics_rf1.py, otherwise XA30

sub=$1
ses=$2

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
dsroot="$(dirname "$scriptdir")"
sourcedata=/ZPOOL/data/sourcedata/sourcedata/rf1-sra

cutoff_epoch=$(date -d '2025-03-04' +%s) # March 4, 2025

if [ "$ses" = "02" ]; then
  folder_sub="${sub}-2"
  subdir="$sourcedata/Smith-SRA-${folder_sub}/Smith-SRA-${folder_sub}"
  scandir="$subdir/scans"

  if [ ! -d "$subdir" ]; then
	  exit 0
  fi

  if ! find "$scandir" -type f -name '*.dcm' -print -quit 2>/dev/null | grep -q .; then
    echo "No ses-02 for sub-${sub}. Skipping ses-${ses}."
    exit 0
  fi
  
  heuristics_file="/out/code/heuristics_XA30.py"
  dicom_template="/sourcedata/Smith-SRA-{subject}-2/Smith-SRA-{subject}-2/scans/*/*/DICOM/files/*.dcm"
  seen="XA30 heuristic, session 2"

else
  folder_sub="${sub}"
  dicom_template="/sourcedata/Smith-SRA-{subject}/Smith-SRA-{subject}/scans/*/*/DICOM/files/*.dcm"
  subdir="$sourcedata/Smith-SRA-${folder_sub}/Smith-SRA-${folder_sub}"
  scandir="$subdir/scans"
  epoch=$(find "$scandir" -type f -name '*.dcm' -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | awk '{print int($1)}' || true)
  [ -z "${epoch:-}" ] && epoch=$(stat -c %Y "$subdir" 2>/dev/null || echo 0)
  if [ "$epoch" -le "$cutoff_epoch" ]; then
    heuristics_file="/out/code/heuristics_rf1.py"
  else
    heuristics_file="/out/code/heuristics_XA30.py"
  fi
  seen="$(date -d "@$epoch" '+%Y-%m-%d %H:%M:%S')"
fi

echo "Heuristic chosen for sub-${sub} ses-${ses}: $(basename "$heuristics_file") [seen=${seen}]"

subdir=$sourcedata/Smith-SRA-${folder_sub}/Smith-SRA-${folder_sub}
scandir=$subdir/scans
locdir=$sourcedata/localizers/Smith-SRA-$folder_sub

if [ ! -d "$locdir" ]; then
  mkdir -p "$locdir"
fi

for localizers in "$scandir"/*-localizer; do
  [ -d "$localizers" ] || continue
  echo "Moving $localizers to $locdir"
  mv "$localizers" "$locdir/"
done

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

# PART 3: MRIQC 
# Create derivatives/mriqc and scratch, then run MRIQC for this subject/session.
#if [ ! -d "$dsroot/derivatives/mriqc" ]; then
#  mkdir -p "$dsroot/derivatives/mriqc"
#fi
#
#scratch=/ZPOOL/data/scratch/$(whoami)
#if [ ! -d "$scratch" ]; then
#  mkdir -p "$scratch"
#fi
#
# TemplateFlow for MRIQC inside the container
#TEMPLATEFLOW_DIR=/ZPOOL/data/tools/templateflow
#export SINGULARITYENV_TEMPLATEFLOW_HOME=/opt/templateflow
#
#echo "Running MRIQC for sub-${sub} ses-${ses}"
#singularity run --cleanenv \
#  -B "${TEMPLATEFLOW_DIR}:/opt/templateflow" \
#  -B "$dsroot/bids:/data" \
#  -B "$dsroot/derivatives/mriqc:/out" \
#  -B "$scratch:/scratch" \
#  /ZPOOL/data/tools/mriqc-24.0.2.simg \
#  /data /out participant \
#  --participant_label "$sub" \
#  --session-id "$ses" \
#  -w /scratch

