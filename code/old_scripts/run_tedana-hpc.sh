#!/bin/bash

# ensure paths are correct
#maindir=~/work/rf1-sra-data #this should be the only line that has to change if the rest of the script is set up correctly
maindir=/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2
scriptdir=$maindir/code


mapfile -t myArray < ${scriptdir}/sublist_new.txt
# sublist_check.txt
#newsubs_rf1-sra-data.txt


ntasks=1
counter=0
while [ $counter -lt ${#myArray[@]} ]; do
	subjects=${myArray[@]:$counter:$ntasks}
	echo $subjects
	let counter=$counter+$ntasks
	qsub -v subjects="${subjects[@]}" tedana-hpc.sh
done
