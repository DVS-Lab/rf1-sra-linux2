#!/bin/bash
#PBS -l walltime=24:00:00
#PBS -N fmriprep-rf1
#PBS -M melanie.kos@temple.edu
#PBS -q normal
#PBS -l nodes=1:ppn=28

source $FSLDIR/etc/fslconf/fsl.sh
module load singularity
cd $PBS_O_WORKDIR

# ── Project paths ──────────────────────────────────────────────────────────────
projectname=rf1-sra-linux2
parentdir=/gpfs/scratch/tug87422/smithlab-shared
maindir=$parentdir/$projectname
scriptdir=$maindir/code
bidsdir=$maindir/bids
logdir=$maindir/logs
mkdir -p "$logdir"

# Make derivatives/fmriprep root if missing
derivdir=$maindir/derivatives/fmriprep-25
mkdir -p "$derivdir"

# Scratch/work space
scratchdir=~/scratch/$projectname/fmriprep-25
mkdir -p "$scratchdir"

# Templateflow & MPL config inside the container
TEMPLATEFLOW_DIR=$parentdir/tools/templateflow
MPLCONFIGDIR_DIR=$parentdir/tools/mplconfigdir
export SINGULARITYENV_TEMPLATEFLOW_HOME=/opt/templateflow
export SINGULARITYENV_MPLCONFIGDIR=/opt/mplconfigdir

# Command list for torque-launch
cmdfile=$logdir/cmd_fmriprep_${PBS_JOBID}.txt
chkfile=$logdir/chk_fmriprep_${PBS_JOBID}.txt
: > "$cmdfile"

# subjects is expected to be defined upstream (e.g., via qsub -v or wrapper)
# If you prefer, uncomment the next line to accept an array passed by index expansion
# subjects=("${!1}")

# ── Per-subject, per-session scheduling ────────────────────────────────────────
for sub in ${subjects[@]}; do
  for ses in ses-01 ses-02; do
    # Only run if the session directory exists in BIDS
    if [ -d "$bidsdir/sub-${sub}/${ses}" ]; then
      # Give each subject x session its own workdir to avoid clashes
      workdir="${scratchdir}/sub-${sub}_${ses}"
      mkdir -p "$workdir"
      ses_num="${ses##ses-}"

      # fmriprep write to /base/derivatives/fmriprep/sub-####/ses-##
      echo singularity run --cleanenv \
        -B ${TEMPLATEFLOW_DIR}:/opt/templateflow \
        -B ${MPLCONFIGDIR_DIR}:/opt/mplconfigdir \
        -B $maindir:/base \
        -B $parentdir/tools/licenses:/opts \
        -B $scratchdir:/scratch \
        $parentdir/tools/fmriprep-25.2.3.simg \
        /base/bids /base/derivatives/fmriprep-25 \
        participant \
        --participant-label ${sub} \
        --session-label ${ses_num} \
        --stop-on-first-crash \
        --skip-bids-validation \
        --nthreads 14 \
        --me-output-echos \
        --output-spaces T1w MNI152NLin6Asym \
        --bids-filter-file /base/code/fmriprep_config.json \
        --fs-no-reconall \
        --fs-license-file /opts/fs_license.txt \
        -w /scratch/sub-${sub}_${ses} >> "$cmdfile"
    fi
  done
done

# Launch queued commands
torque-launch -p "$chkfile" "$cmdfile"

# Optional flags you might want later:
# --cifti-output 91k
# --output-spaces fsLR fsaverage MNI152NLin6Asym

