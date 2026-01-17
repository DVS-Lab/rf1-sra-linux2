import os
import json
import glob

# Define paths
sublist_file = '/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/code/sublist_all.txt'
output_file = 'mriqc-metrics_allTasks_n299_ses-01.csv'
tasks = ['ugr', 'doors', 'socialdoors', 'trust', 'sharedreward']  # List of tasks

# Read the subject IDs from sublist-all.txt
with open(sublist_file, 'r') as f:
    subjects = f.read().splitlines()

# Prepare to collect results
results = []

# Iterate through subjects and tasks
for sub in subjects:
    for task in tasks:
        # 5-digit subject format
        json_pattern = f'/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/derivatives/mriqc/sub-{sub}/ses-01/func/sub-{sub}_ses-01_task-{task}_run-*_' \
                       f'echo-2_part-mag_bold.json'

        # Find JSON files
        json_files = glob.glob(json_pattern)
        
        # Iterate through the runs for each subject
        for json_file in json_files:
            run = json_file.split('_run-')[-1].split('_')[0]  # Extract run number from the filename
            tsnr = 'missing'
            fd_mean = 'missing'
            
            try:
                # Read JSON file
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Extract tsnr and fd_mean, ensuring they're strings
                tsnr = str(data.get('tsnr', 'missing'))
                fd_mean = str(data.get('fd_mean', 'missing'))
            except Exception as e:
                # If an error occurs, keep the default 'missing' values
                print(f"Error reading {json_file}: {e}")
            
            # Append the result to the results list
            results.append([sub, task, run, tsnr, fd_mean])

# Write results to CSV file
with open(output_file, 'w') as f:
    f.write('sub,task,run,tsnr,fd_mean\n')
    for result in results:
        f.write(','.join(map(str, result)) + '\n')

print(f"Results saved to {output_file}")

