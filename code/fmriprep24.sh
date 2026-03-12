# Paths
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
maindir="$(dirname "$scriptdir")"
bidsdir=$maindir/bids
logdir=$maindir/logs
tooldir=/ZPOOL/data/tools
mkdir -p $logdir

# Derivatives, scratch, log file
if [ ! -d $maindir/derivatives ]; then
    mkdir -p $maindir/derivatives
fi

# Scratch dir under your account (not in ZPOOL) on linux
scratchdir="$HOME/scratch"
mkdir -p "$scratchdir"

logfile=${logdir}/fmriprep24_output.log
touch ${logfile}

export SINGULARITYENV_TEMPLATEFLOW_HOME=/opt/templateflow
export SINGULARITYENV_MPLCONFIGDIR=/opt/mplconfigdir

# Subjects come from wrapper
# Loop sessions; only runs if the session dir exists
for sub in $subjects; do
  for ses in 01 02; do
    if [ -d "$bidsdir/sub-${sub}/ses-${ses}" ]; then
	    cfg="/base/code/ses-${ses}.json"      # per-session filter json keeps ANAT/FUNC/FMAP to that session
	    # Make scratch dir for sub and session being processed
	    workdir="$scratchdir/fmriprep-24/sub-${sub}_ses-${ses}"
	    mkdir -p "$workdir"
     
      singularity run --cleanenv \
        -B ${tooldir}/templateflow:/opt/templateflow \
        -B ${tooldir}/mplconfigdir:/opt/mplconfigdir \
        -B $maindir:/base \
        -B ${tooldir}/licenses:/opts \
        -B $scratchdir:/scratch \
        ${tooldir}/fmriprep-24.1.1.simg \
        /base/bids /base/derivatives/fmriprep-24 \
        participant --participant_label $sub \
        --stop-on-first-crash \
        --skip-bids-validation \
        --nthreads 12 \
	--omp-nthreads 8 \
        --me-output-echos \
        --output-spaces MNI152NLin6Asym \
        --bids-filter-file $cfg \
        --fs-no-reconall \
        --fs-license-file /opts/fs_license.txt \
        -w "/scratch/fmriprep24_sub-${sub}_ses-${ses}" \
        >> "$logfile" 2>&1
    fi
  done
done

