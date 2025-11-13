#!/bin/bash
#PBS -l walltime=24:00:00
#PBS -N warpkit
#PBS -q normal
#PBS -l nodes=1:ppn=28

# ── Paths ────────────────────────────────────────────────────────
maindir=/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2
toolsdir=/gpfs/scratch/tug87422/smithlab-shared/tools
scriptdir=$maindir/code
logdir=$maindir/logs
mkdir -p "$logdir"
touch "$scriptdir/missingFiles-warpkit.log"

# ── Modules / env ────────────────────────────────────────────────
module load singularity
FSLDIR="$toolsdir/fsl"
source "$FSLDIR/etc/fslconf/fsl.sh"
RUNTIME=/gpfs/opt/tools/apptainer-1.2.4/bin/singularity
umask 0000

# Clean old PBS stdout/err logs (not the per-task logs)
rm -rf "$scriptdir"/warpkit.o* "$scriptdir"/warpkit.e*

# Templateflow / MPL config (propagated into container)
TEMPLATEFLOW_DIR=$toolsdir/templateflow
MPLCONFIGDIR_DIR=$toolsdir/mplconfigdir
export SINGULARITYENV_TEMPLATEFLOW_HOME=/opt/templateflow
export SINGULARITYENV_MPLCONFIGDIR=/opt/mplconfigdir

# If PBS_JOBID is empty (manual run), use PID so filenames aren’t blank
JOBID=${PBS_JOBID:-manual$$}

# Rehydrate the "subjects" env string (passed by qsub -v) into an array
IFS=' ' read -r -a subjects <<< "$subjects"

# ── Main loops ───────────────────────────────────────────────────
for sub in "${subjects[@]}"; do
  # Build the sessions list dynamically from existing BIDS folders (no phantom ses-02)
  sessions=()
  for s in ses-01 ses-02; do
    if [[ -d "$maindir/bids/sub-${sub}/${s}/func" ]]; then
      sessions+=("$s")
    fi
  done
  if [[ ${#sessions[@]} -eq 0 ]]; then
    echo "[SKIP] sub-$sub has no ses-01/ses-02 func directories"
    continue
  fi

  for ses in "${sessions[@]}"; do
    for task in sharedreward trust ugr doors socialdoors; do
      for run in 1 2; do

        # Doors/SocialDoors only have run-1
        if [[ "$task" == "doors" || "$task" == "socialdoors" ]]; then
          run=1
        fi

        # Paths (do NOT create any directories yet)
        indir="$maindir/bids/sub-${sub}/${ses}/func"
        fmapdir="$maindir/bids/sub-${sub}/${ses}/fmap"
        outdir="$maindir/derivatives/warpkit/sub-${sub}/${ses}"

        # Input presence check
        if [[ ! -e "$indir/sub-${sub}_${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json" ]]; then
          echo "NO DATA: sub-${sub}_${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json"
          echo "NO DATA: sub-${sub}_${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json" >> "$scriptdir/missingFiles-warpkit.log"
          continue
        fi

        # Don't redo existing output
        if [[ -e "$fmapdir/sub-${sub}_${ses}_acq-${task}_run-${run}_fieldmap.nii.gz" ]]; then
          echo "EXISTS (skipping): sub-${sub}/${ses}/fmap/sub-${sub}_${ses}_acq-${task}_run-${run}_fieldmap.nii.gz"
          continue
        fi

        # Verify all 12 multi-echo inputs exist
        missing=0
        for e in 1 2 3 4; do
          for kind in part-mag_bold.nii.gz part-phase_bold.nii.gz part-phase_bold.json; do
            f="$indir/sub-${sub}_${ses}_task-${task}_run-${run}_echo-${e}_${kind}"
            if [[ ! -e "$f" ]]; then
              echo "MISSING: $f" | tee -a "$scriptdir/missingFiles-warpkit.log"
              missing=1
            fi
          done
        done
        if [[ $missing -eq 1 ]]; then
          echo "[SKIP] sub-$sub $ses $task run-$run due to missing inputs"
          continue
        fi

        # Now that we KNOW we’ll run, create the output dirs (no earlier!)
        mkdir -p "$outdir" "$fmapdir"

        # Delete default GRE phasediff maps, if present
        if [[ -e "$fmapdir/sub-${sub}_${ses}_acq-bold_phasediff.nii.gz" ]]; then
          rm -f "$fmapdir"/sub-${sub}_${ses}_acq-bold*
        fi

        # Per-task command file + log
        cmdfile="$logdir/cmd_warpkit_${sub}_${ses}_${task}_${run}_${JOBID}.txt"
        joblog="$logdir/warpkit_${sub}_${ses}_${task}_${run}.log"
        rm -f "$cmdfile"
        touch "$cmdfile"

        # Build single-line command that runs warpkit AND then extracts/copies outputs
        echo "set -o pipefail; \
$RUNTIME run --cleanenv \
  -B $indir:/base \
  -B $outdir:/out \
  -B $TEMPLATEFLOW_DIR:/opt/templateflow \
  -B $MPLCONFIGDIR_DIR:/opt/mplconfigdir \
  $toolsdir/warpkit.sif \
  --magnitude /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.nii.gz \
             /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-2_part-mag_bold.nii.gz \
             /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-3_part-mag_bold.nii.gz \
             /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-4_part-mag_bold.nii.gz \
  --phase    /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-1_part-phase_bold.nii.gz \
             /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-2_part-phase_bold.nii.gz \
             /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-3_part-phase_bold.nii.gz \
             /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-4_part-phase_bold.nii.gz \
  --metadata /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-1_part-phase_bold.json \
             /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-2_part-phase_bold.json \
             /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-3_part-phase_bold.json \
             /base/sub-${sub}_${ses}_task-${task}_run-${run}_echo-4_part-phase_bold.json \
  --out_prefix /out/sub-${sub}_${ses}_task-${task}_run-${run} \
  -n 1 -f 4 \
  2>&1 | tee -a $joblog \
&& fslroi $outdir/sub-${sub}_${ses}_task-${task}_run-${run}_fieldmaps.nii \
          $fmapdir/sub-${sub}_${ses}_acq-${task}_run-${run}_fieldmap.nii.gz 0 1 \
&& fslroi $indir/sub-${sub}_${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.nii.gz \
          $fmapdir/sub-${sub}_${ses}_acq-${task}_run-${run}_magnitude.nii.gz 0 1 \
&& cp $indir/sub-${sub}_${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json \
      $fmapdir/sub-${sub}_${ses}_acq-${task}_run-${run}_magnitude.json \
&& cp $indir/sub-${sub}_${ses}_task-${task}_run-${run}_echo-1_part-phase_bold.json \
      $fmapdir/sub-${sub}_${ses}_acq-${task}_run-${run}_fieldmap.json \
&& rm -f $outdir/sub-${sub}_${ses}_task-${task}_run-${run}_displacementmaps.nii \
         $outdir/sub-${sub}_${ses}_task-${task}_run-${run}_fieldmaps_native.nii" >> "$cmdfile"

        # Launch the command
        torque-launch -p "$logdir/chk_warpkit_${sub}_${ses}_${task}_${run}_${JOBID}.txt" "$cmdfile"

      done
    done
  done
done

