%% Convert SocialDoors raw behavioral to BIDS events
%% Edited by Melanie Kos, 2026. 
% This version of the script converts raw behavioral event data
% (from rf1-sra/stimuli) into BIDS-compatible .tsv files for 
% rf1-sra-linux2. It handles both wave/session labels: 
% ses-01 indicates Wave 1, ses-02 indicates Wave 2.
% This script searches through each subject's behavioral data for available
% SocialDoors and Doors event files and writes all files to the bids func 
% directory, even if a run is behaviorally invalid. Behavioral validity 
% is tracked separately through printed summaries and subject lists. 
% A valid run is defined as one where the participant responded to at
% least 75% of decision trials, (i.e., fewer than 10/40 trials missed).
% Subject lists should be used as the reference point for determining 
% which subjects/runs are valid for FSL analyses, especially L3 analyses. 
% The script also outputs to the MATLAB console information on any missing 
% SocialDoors or Doors behavioral data for MR subjects. For example, 
% this can help identify cases where a subject was collected under the 
% incorrect subject ID on the MR computer or stimulus PC. 

% This logic for this script is based on the UGR convert script, 
% which has this same basic setup.

% Outputs are BIDS-compatible event files (output to bids/) and 
% valid behavior subject lists (output to code/).

% set relative directories
filePath = matlab.desktop.editor.getActiveFilename;
[codedir,name,ext] = fileparts(filePath);
[projectdir,~,~] = fileparts(codedir);

% Change paths as needed (i.e., all_subjects_file to your sublist of interest)
basedir = '/ZPOOL/data/projects/rf1-sra-linux2';
datadir = '/ZPOOL/data/projects/rf1-sra/stimuli/Scan-Social_Doors/data';
all_subjects_file = '/ZPOOL/data/projects/rf1-sra-socdoors/code/sublist-datapush.txt';

% load subject list from folder names
subject_files = dir(fullfile(datadir, '1*'));
subjects = {subject_files.name};
disp(length(subjects))

% session info: BIDS output label, possible input filename tags
% ses-01: files either have no session tag OR explicit 'ses-1' / 'ses-01'
% ses-02: files always have explicit 'ses-02'
sess_info = {
    'ses-01', {'', '_ses-1', '_ses-01'};
    'ses-02', {'_ses-02'};
};

% A/B indicates face set, not session-specific 
task_letters = {'A', 'B'};

% task types and their BIDS names
task_types = {
    'faces', 'socialdoors';
    'doors', 'doors';
};

for s = 1:length(subjects)
    disp(["Now converting", subjects{s}, "events to BIDS format"]);
    inputdir = fullfile(datadir, subjects{s});

    for sess_i = 1:size(sess_info, 1)
        sess      = sess_info{sess_i, 1};   % 'ses-01' or 'ses-02'
        sess_tags = sess_info{sess_i, 2};   % cell array of possible input tags
        
        for tk = 1:size(task_types, 1)
            rawtask  = task_types{tk, 1};   % 'faces' or 'doors'
            bidstask = task_types{tk, 2};   % 'socialdoors' or 'doors'

            % Search for input file across possible session tags, task letters, and image sets (1-4)
            indata = '';
            for tag_i = 1:length(sess_tags)
                for letter_i = 1:length(task_letters)
                    task_letter = task_letters{letter_i};
                    for img_set = 1:4
                        rawtask_full = sprintf('%s%s%d', rawtask, task_letter, img_set);
                        cand = fullfile(inputdir, ... 
                            sprintf('sub-%s%s_task-socialReward_%s_events.tsv', ...
                            subjects{s}, sess_tags{tag_i}, rawtask_full));

                        if exist(cand, 'file')
                            indata = cand;
                            break
                        end
                    end

                    if ~isempty(indata), break; end
                end

                if ~isempty(indata), break; end
            end

            if isempty(indata)
                % quiet skip if file not present for this session/task
                continue
            end

            % Read data
            T = readtable(indata, 'FileType', 'delimitedtext', 'Delimiter', '\t');

            % Check behavioral validity, but still write all found runs to BIDS.
            % Validity is tracked later through the subject-list outputs.
            decision_rows  = strcmp(T.trial_type, 'decision');
            missed_rows    = strcmp(T.trial_type, 'decision-missed');
            n_decision     = sum(decision_rows) + sum(missed_rows);
            n_missed       = sum(missed_rows);

            if n_decision ~= 40
                disp(['  WARNING: unexpected trial count (' num2str(n_decision) '/40 decision rows, still writing to BIDS): ' indata])
            elseif n_missed >= 10
                disp(['  WARNING: too many missed trials (' num2str(n_missed) '/40) - invalid run, still writing to BIDS: ' indata])
            else
                disp(['  Valid behavioral run (' num2str(n_missed) '/40 missed): ' indata])
            end

            % Build BIDS output path
            sub_str = subjects{s};
            bidsdir = fullfile(basedir, 'bids', ['sub-' sub_str], sess, 'func');
            bidsname = fullfile(bidsdir, ...
                sprintf('sub-%s_%s_task-%s_run-1_events.tsv', sub_str, sess, bidstask));

            if ~exist(bidsdir, 'dir')
                mkdir(bidsdir);
            end

            writetable(T, bidsname, 'FileType', 'text', 'Delimiter', '\t');
            disp(['    Written: ' bidsname]);
        end
    end
end

%% Validity checking — track validity separately by session and task

subjects_all_invalid     = {};
subjects_one_invalid     = {};
subjects_with_valid_data = {};

ses1_bad_runs = {};
ses2_bad_runs = {};

% 5 output subject lists: ses1 valid socialdoors and doors (both tasks)
% ses2 both tasks valid, ses1 and 2 (both sessions) valid socialdoors, 
% both sessions valid doors, and both sessions both tasks valid
ses1_both_tasks_valid_subjects = {};
ses2_both_tasks_valid_subjects = {};
socialdoors_both_sessions_valid_subjects = {};
doors_both_sessions_valid_subjects = {};
both_tasks_both_sessions_valid_subjects = {};

for s = 1:length(subjects)
    subject_id = subjects{s};
    inputdir   = fullfile(datadir, subject_id);

    % validity matrix:
    % rows = sessions (1=ses-01, 2=ses-02)
    % cols = tasks    (1=socialdoors/faces, 2=doors)
    valid_matrix   = false(2,2);
    present_matrix = false(2,2);
    status_msgs    = cell(2,2);

    for sess_i = 1:size(sess_info, 1)
        sess      = sess_info{sess_i, 1};
        sess_tags = sess_info{sess_i, 2};

        for tk = 1:size(task_types, 1)
            rawtask  = task_types{tk, 1};
            bidstask = task_types{tk, 2};

            % Search for input file across possible session tags, task letters, and image sets
            indata = '';
            for tag_i = 1:length(sess_tags)
                for letter_i = 1:length(task_letters)
                    task_letter = task_letters{letter_i};
                    for img_set = 1:4
                        rawtask_full = sprintf('%s%s%d', rawtask, task_letter, img_set);
                        cand = fullfile(inputdir, ...
                            sprintf('sub-%s%s_task-socialReward_%s_events.tsv', ...
                            subject_id, sess_tags{tag_i}, rawtask_full));

                        if exist(cand, 'file')
                            indata = cand;
                            break
                        end
                    end

                    if ~isempty(indata), break; end
                end

                if ~isempty(indata), break; end
            end

            run_label = sprintf('%s task-%s', sess, bidstask);

            if isempty(indata)
                status_msgs{sess_i, tk} = sprintf('%s: MISSING', run_label);
                continue
            end

            present_matrix(sess_i, tk) = true;

            T = readtable(indata, 'FileType', 'delimitedtext', 'Delimiter', '\t');

            decision_rows = strcmp(T.trial_type, 'decision');
            missed_rows   = strcmp(T.trial_type, 'decision-missed');
            n_decision    = sum(decision_rows) + sum(missed_rows);
            n_missed      = sum(missed_rows);

            if n_decision ~= 40
                msg = sprintf('%s: INVALID (unexpected trial count %d/40)', run_label, n_decision);
                status_msgs{sess_i, tk} = msg;

                if strcmp(sess, 'ses-01')
                    ses1_bad_runs{end+1} = sprintf('Subject %s - %s', subject_id, msg);
                else
                    ses2_bad_runs{end+1} = sprintf('Subject %s - %s', subject_id, msg);
                end

                continue
            end

            if n_missed >= 10
                msg = sprintf('%s: INVALID (%d/40 missed)', run_label, n_missed);
                status_msgs{sess_i, tk} = msg;

                if strcmp(sess, 'ses-01')
                    ses1_bad_runs{end+1} = sprintf('Subject %s - %s', subject_id, msg);
                else
                    ses2_bad_runs{end+1} = sprintf('Subject %s - %s', subject_id, msg);
                end
            else
                msg = sprintf('%s: VALID (%d/40 missed)', run_label, n_missed);
                status_msgs{sess_i, tk} = msg;
                valid_matrix(sess_i, tk) = true;
            end
        end
    end

    % Flatten messages for summary printing
    subject_msgs = {};
    for sess_i = 1:2
        for tk = 1:2
            if ~isempty(status_msgs{sess_i, tk})
                subject_msgs{end+1} = status_msgs{sess_i, tk};
            end
        end
    end

    num_valid   = sum(valid_matrix(:));
    num_present = sum(present_matrix(:));

    if num_valid == 0 && num_present > 0
        subjects_all_invalid{end+1} = sprintf('Subject %s - %s', subject_id, strjoin(subject_msgs, ', '));
    elseif num_valid > 0 && num_valid < num_present
        subjects_one_invalid{end+1} = sprintf('Subject %s - %s', subject_id, strjoin(subject_msgs, ', '));
        subjects_with_valid_data{end+1} = subject_id;
    elseif num_valid > 0
        subjects_with_valid_data{end+1} = subject_id;
    end

    % Requested outputs

    % BOTH SocialDoors + Doors valid within ses-01
    if valid_matrix(1,1) && valid_matrix(1,2)
        ses1_both_tasks_valid_subjects{end+1} = subject_id;
    end

    % BOTH SocialDoors + Doors valid within ses-02
    if valid_matrix(2,1) && valid_matrix(2,2)
        ses2_both_tasks_valid_subjects{end+1} = subject_id;
    end

    % SocialDoors valid in BOTH sessions
    if valid_matrix(1,1) && valid_matrix(2,1)
        socialdoors_both_sessions_valid_subjects{end+1} = subject_id;
    end

    % Doors valid in BOTH sessions
    if valid_matrix(1,2) && valid_matrix(2,2)
        doors_both_sessions_valid_subjects{end+1} = subject_id;
    end

    % Optional: BOTH tasks valid in BOTH sessions
    if all(valid_matrix(:))
        both_tasks_both_sessions_valid_subjects{end+1} = subject_id;
    end
end

%% Print summaries to console

disp('Subjects with ALL invalid runs (exclude subject):');
for i = 1:length(subjects_all_invalid)
    fprintf('%s\n', subjects_all_invalid{i});
end

disp('Subjects with at least one invalid/missing run but some valid data:');
for i = 1:length(subjects_one_invalid)
    fprintf('%s\n', subjects_one_invalid{i});
end

disp('ses-01 BAD behavioral runs:');
for i = 1:length(ses1_bad_runs)
    fprintf('%s\n', ses1_bad_runs{i});
end

disp('ses-02 BAD behavioral runs:');
for i = 1:length(ses2_bad_runs)
    fprintf('%s\n', ses2_bad_runs{i});
end

disp('Subjects with at least one valid run (any session/task):');
for i = 1:length(subjects_with_valid_data)
    fprintf('%s\n', subjects_with_valid_data{i});
end

disp('ses-01: subjects with BOTH SocialDoors and Doors valid:');
for i = 1:length(ses1_both_tasks_valid_subjects)
    fprintf('%s\n', ses1_both_tasks_valid_subjects{i});
end

disp('ses-02: subjects with BOTH SocialDoors and Doors valid:');
for i = 1:length(ses2_both_tasks_valid_subjects)
    fprintf('%s\n', ses2_both_tasks_valid_subjects{i});
end

disp('Subjects with valid SocialDoors in BOTH sessions:');
for i = 1:length(socialdoors_both_sessions_valid_subjects)
    fprintf('%s\n', socialdoors_both_sessions_valid_subjects{i});
end

disp('Subjects with valid Doors in BOTH sessions:');
for i = 1:length(doors_both_sessions_valid_subjects)
    fprintf('%s\n', doors_both_sessions_valid_subjects{i});
end

disp('Subjects with BOTH SocialDoors and Doors valid in BOTH sessions:');
for i = 1:length(both_tasks_both_sessions_valid_subjects)
    fprintf('%s\n', both_tasks_both_sessions_valid_subjects{i});
end

%% Write behavioral-validity summaries to ignored logs/
valid_output_dir = fullfile(basedir, 'logs', 'behavior-validity');
if ~exist(valid_output_dir, 'dir')
    mkdir(valid_output_dir);
end

% ses-01 both tasks valid
valid_output_file_ses1_both = fullfile(valid_output_dir, 'ses-01_valid-socialdoors-and-doors.txt');
fid = fopen(valid_output_file_ses1_both, 'w');
for i = 1:length(ses1_both_tasks_valid_subjects)
    fprintf(fid, '%s\n', ses1_both_tasks_valid_subjects{i});
end
fclose(fid);
disp(['Saved ses-01 BOTH-task valid subject list to: ' valid_output_file_ses1_both]);

% ses-02 both tasks valid
valid_output_file_ses2_both = fullfile(valid_output_dir, 'ses-02_valid-socialdoors-and-doors.txt');
fid = fopen(valid_output_file_ses2_both, 'w');
for i = 1:length(ses2_both_tasks_valid_subjects)
    fprintf(fid, '%s\n', ses2_both_tasks_valid_subjects{i});
end
fclose(fid);
disp(['Saved ses-02 BOTH-task valid subject list to: ' valid_output_file_ses2_both]);

% SocialDoors valid in both sessions
valid_output_file_socialdoors_both_sessions = fullfile(valid_output_dir, 'both-sessions_valid-socialdoors.txt');
fid = fopen(valid_output_file_socialdoors_both_sessions, 'w');
for i = 1:length(socialdoors_both_sessions_valid_subjects)
    fprintf(fid, '%s\n', socialdoors_both_sessions_valid_subjects{i});
end
fclose(fid);
disp(['Saved BOTH-sessions SocialDoors valid subject list to: ' valid_output_file_socialdoors_both_sessions]);

% Doors valid in both sessions
valid_output_file_doors_both_sessions = fullfile(valid_output_dir, 'both-sessions_valid-doors.txt');
fid = fopen(valid_output_file_doors_both_sessions, 'w');
for i = 1:length(doors_both_sessions_valid_subjects)
    fprintf(fid, '%s\n', doors_both_sessions_valid_subjects{i});
end
fclose(fid);
disp(['Saved BOTH-sessions Doors valid subject list to: ' valid_output_file_doors_both_sessions]);

% Optional: both tasks valid in both sessions
valid_output_file_all_valid = fullfile(valid_output_dir, 'both-sessions_valid-socialdoors-and-doors.txt');
fid = fopen(valid_output_file_all_valid, 'w');
for i = 1:length(both_tasks_both_sessions_valid_subjects)
    fprintf(fid, '%s\n', both_tasks_both_sessions_valid_subjects{i});
end
fclose(fid);
disp(['Saved BOTH-sessions BOTH-task valid subject list to: ' valid_output_file_all_valid]);

%% Check for MR subjects missing all runs
missing_subjects = {};
% Read subject list (replaces deprecated textread)
all_subjects = cellstr(strtrim(readlines(all_subjects_file)));
all_subjects = all_subjects(~cellfun(@isempty, all_subjects));

for i = 1:length(all_subjects)
    subject  = all_subjects{i};
    inputdir = fullfile(datadir, subject);
    found    = false;

    for sess_i = 1:size(sess_info, 1)
        sess_tags = sess_info{sess_i, 2};

        for tk = 1:size(task_types, 1)
            rawtask = task_types{tk, 1};

            for tag_i = 1:length(sess_tags)
                for letter_i = 1:length(task_letters)
                    task_letter = task_letters{letter_i};
                    for img_set = 1:4
                        rawtask_full = sprintf('%s%s%d', rawtask, task_letter, img_set);
                        cand = fullfile(inputdir, ...
                            sprintf('sub-%s%s_task-socialReward_%s_events.tsv', ...
                            subject, sess_tags{tag_i}, rawtask_full));

                        if exist(cand, 'file')
                            found = true;
                            break
                        end
                    end

                    if found, break; end
                end

                if found, break; end
            end

            if found, break; end
        end

        if found, break; end
    end

    if ~found
        missing_subjects{end+1} = subject;
    end
end

disp('MR subjects missing all SocialDoors/Doors data:');
for i = 1:length(missing_subjects)
    fprintf('%s\n', missing_subjects{i});
end
