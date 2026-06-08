# Originally by Cooper Sharp, edited by Melanie Kos
# This script extracts MRIQC data (i.e., fd_mean, tsnr) for L3 analyses
# Customize to get output .csv file based on your sublist, session(s) of interest, and tasks

import os
import json
import glob
import csv

# Define paths (customize these paths as needed, all else should remain untouched)
base_dir = '/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2'
sublist_file = f'{base_dir}/code/sublist_all.txt'
output_file = f'{base_dir}/code/mriqc-metrics_allTasks_ses-01-02.csv'
sessions = ['01', '02']
tasks = ['ugr', 'doors', 'socialdoors', 'trust', 'sharedreward']

# Read subjects from sublist_file
with open(sublist_file, 'r') as f:
    subjects = f.read().splitlines()

# List to store results
results = []

# Iterate through subjects, sessions, and tasks
for sub in subjects:
    for ses in sessions:
        for task in tasks:
            # Using echo 2 (can be hardcoded to use any of the other echoes)
            json_pattern = f'{base_dir}/derivatives/mriqc/sub-{sub}/ses-{ses}/func/sub-{sub}_ses-{ses}_task-{task}_run-*_echo-2_part-mag_bold.json'

            # Find json files
            json_files = sorted(glob.glob(json_pattern))
            
            # Iterate through the runs for each subjects
            for json_file in json_files:
                run = json_file.split('_run-')[-1].split('_')[0]
                tsnr = 'missing'
                fd_mean = 'missing'

                try:
                    # Read json file
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                        
                    # Extract tsnr and fd_mean, ensuring they're strings
                    tsnr = data.get('tsnr', 'missing')
                    fd_mean = data.get('fd_mean', 'missing')

                except Exception as e:
                    print(f"Error reading {json_file}: {e}")

                # Append to results list
                results.append({'subject': sub,
                                'session': f'ses-{ses}',
                                'task': task,
                                'run': run,
                                'tsnr': tsnr,
                                'fd_mean': fd_mean,
                                'json_file': json_file})

# Write output CSV
with open(output_file, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['subject', 'session', 'task', 'run', 'tsnr', 'fd_mean', 'json_file'])
    writer.writeheader()
    writer.writerows(results)

print(f"Saved MRIQC metrics to: {output_file}")

