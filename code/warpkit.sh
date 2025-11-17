#!/bash/bin
set -euo pipefail

# NOTE: THIS IS THE SESSION-ENCODING VERSION OF WARPKIT. 


# ensure paths are correct irrespective from where user runs the script
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
maindir="$(dirname "$scriptdir")"
logdir=${maindir}/logs
if [ ! -d "$logdir" ]; then
	mkdir -p "$logdir"
fi

sub=$1
ses=$2
task=$3
run=$4

# If no session 2, don't run session-02 commands
if [ "$ses" == "02" ] &&  [ ! -d "${maindir}/bids/sub-${sub}/ses-02" ]; then
    exit 0
fi

indir=${maindir}/bids/sub-${sub}/ses-${ses}/func

# Log missing data
if [ ! -e "$indir/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json" ]; then
    echo "NO DATA: sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json"
    echo "NO DATA: sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json" >> "$logdir/missingFiles-warpkit.log"
    exit 0
fi

# Output warpkit folder
outdir=$maindir/derivatives/warpkit/sub-${sub}/ses-${ses}
if [ ! -d "$outdir" ]; then
    mkdir -p "$outdir"
fi


# don't re-do existing output
if [ -e $maindir/bids/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap.nii.gz ]; then
	echo "EXISTS (skipping): sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap.nii.gz"
	exit
fi

# delete default gre fmaps (phasediff)
if [ -e $maindir/bids/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-bold_phasediff.nii.gz ]; then
	rm -rf $maindir/bids/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-bold*
fi

singularity run --cleanenv \
-B $indir:/base \
-B $outdir:/out \
/ZPOOL/data/tools/warpkit.sif \
--magnitude /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.nii.gz \
			/base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-2_part-mag_bold.nii.gz \
			/base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-3_part-mag_bold.nii.gz \
			/base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-4_part-mag_bold.nii.gz \
--phase /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-phase_bold.nii.gz \
		/base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-2_part-phase_bold.nii.gz \
		/base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-3_part-phase_bold.nii.gz \
		/base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-4_part-phase_bold.nii.gz \
--metadata /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-phase_bold.json \
			/base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-2_part-phase_bold.json \
			/base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-3_part-phase_bold.json \
			/base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-4_part-phase_bold.json \
--out_prefix /out/sub-${sub}_ses-${ses}_task-${task}_run-${run}


# extract first volume as fieldmap and copy to fmap dir. still need json files for these. 
fslroi $outdir/sub-${sub}_ses-${ses}_task-${task}_run-${run}_fieldmaps.nii $maindir/bids/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap 0 1
fslroi $indir/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.nii.gz $maindir/bids/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_magnitude 0 1

# placeholders for json files. will need editing.
cp $indir/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json $maindir/bids/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_magnitude.json
cp $indir/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-phase_bold.json $maindir/bids/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap.json

# trash the rest
rm -rf $outdir/sub-${sub}_ses-${ses}_task-${task}_run-${run}_displacementmaps.nii
rm -rf $outdir/sub-${sub}_ses-${ses}_task-${task}_run-${run}_fieldmaps_native.nii

