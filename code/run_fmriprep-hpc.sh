#!/bin/bash

# ensure paths are correct
maindir=/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2 #this should be the only line that has to change if the rest of the script is set up correctly
scriptdir=$maindir/code


mapfile -t myArray < ${scriptdir}/sublist_new.txt


# grab the first ntask elements
ntasks=1
counter=0
while [ $counter -lt ${#myArray[@]} ]; do
	subjects=${myArray[@]:$counter:$ntasks}
	echo $subjects
	let counter=$counter+$ntasks
	#qsub -v subjects="${subjects[@]}" fmriprep24-hpc.sh
	qsub -v subjects="${subjects[@]}" fmriprep25-hpc.sh
done
