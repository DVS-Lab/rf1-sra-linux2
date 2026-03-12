#!/bin/bash

# ensure paths are correct
# NOTE: MAKE SURE YOU HAVE TEDANA UP TO DATE AND INSTALLED IN YOUR HOME REPO.
projectname=rf1-sra-linux2 #this should be the only line that has to change if the rest of the script is set up correctly
maindir=/ZPOOL/data/projects/$projectname
scriptdir=$maindir/code
bidsdir=$maindir/bids
logdir=$maindir/logs
mkdir -p $logdir
logfile=$logdir/tedana_output.log
missinglog=$scriptdir/missing-tedanaInput.log
touch $logfile
touch $missinglog

# estimated procs per subject: 4 tasks * 2 runs * 4 echoes = 32?
# wow... can't be right, but let's go for 9 subjects per job (84 procs per job). watch for memory issues.
# EDIT: sending only one subject/job currently in the run script
for fmriprep in 24 25; do
  for sub in ${subjects[@]}; do
    for ses in 01 02; do 
	    for task in "socialdoors" "doors" "trust" "sharedreward" "ugr"; do
		    for run in 1 2; do

			    indata=$maindir/derivatives/fmriprep-${fmriprep}/sub-${sub}/ses-${ses}/func
			    echo1=${indata}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_desc-preproc_bold.nii.gz
			    echo2=${indata}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-2_part-mag_desc-preproc_bold.nii.gz
			    echo3=${indata}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-3_part-mag_desc-preproc_bold.nii.gz
			    echo4=${indata}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-4_part-mag_desc-preproc_bold.nii.gz
			    if [ ! -e "$echo1" ] || [ ! -e "$echo2" ] || [ ! -e "$echo3" ] || [ ! -e "$echo4" ]; then
				    echo "Missing one or more files for sub-${sub}, ses-${ses}, task-${task}, run-${run}" >> ${missinglog}
				    echo "Skipping sub-${sub}, ses-${ses}, task-${task}, run-${run}" >> ${logfile}
				    continue
			    fi
			    outdir=$maindir/derivatives/tedana-${fmriprep}/sub-${sub}/ses-${ses}
			    mkdir -p $outdir
			
			    echotime1=""
			    echotime2=""
			    echotime3=""
			    echotime4=""

			    # Extract echos
			    for echo in 1 2 3 4; do
				    bidsfuncdir=$bidsdir/sub-${sub}/ses-${ses}/func
				    json_file=$(find "$bidsfuncdir" -name "sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-${echo}_part-mag_bold.json")
				    if [ -n "$json_file" ]; then
					    echo_time=$(grep -o '"EchoTime": [0-9.]*' "$json_file" | cut -d' ' -f2 | tr -d '\r')
					    eval "echotime${echo}=${echo_time}"
				    else
					    echo "Missing JSON for sub-${sub}, ses-${ses},  task-${task}, run-${run}, echo-${echo}"
					    echo "Missing JSON for sub-${sub}, ses-${ses}, task-${task}, run-${run}, echo-${echo}" >> $scriptdir/missing-tedanaInput.log
				    fi
			    done


			    tedana -d $echo1 $echo2 $echo3 $echo4 \
			    -e $echotime1 $echotime2 $echotime3 $echotime4 \
			    --out-dir $outdir \
			    --prefix sub-${sub}_ses-${ses}_task-${task}_run-${run} \
			    --convention bids \
			    --fittype curvefit \
			    --overwrite \
                >> ${logfile} 2>&1
		    done
	    done
    done		
  done
done

