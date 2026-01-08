clear; close all;
[pathstr,name,ext] = fileparts(pwd);
usedir = pathstr;
maindir = pwd;
input_file_path = fullfile(usedir,'..','rf1-sra-socdoors','stimuli','Scan-Social_Doors','data','renamed_files');

% Convert to absolute path for clarity
input_file_path = char(java.io.File(input_file_path).getCanonicalPath());

warning off all

% DEBUG: Print the key paths
disp(['Current directory (pwd): ', pwd]);
disp(['usedir: ', usedir]);
disp(['input_file_path: ', input_file_path]);

subs = load('sublist_all.txt');

tasks = {'facesA1', 'facesA2','facesA3','facesA4',...
    'facesB1','facesB2','facesB3','facesB4',...
    'doorsA1','doorsA2','doorsA3','doorsA4',...
    'doorsB1','doorsB2','doorsB3','doorsB4'};

% loop through each sub
for s = 1:length(subs)
    disp(["Now converting",subs(s),"events to BIDS format"]);
    
    % DEBUG: Check if subject directory exists
    inputdir = sprintf('%s/%d', input_file_path, subs(s));
    disp(['  Checking directory: ', inputdir]);
    disp(['  Directory exists: ', num2str(exist(inputdir, 'dir'))]);
    
    for t = 1:length(tasks)
        rawtask = tasks{t};

        % rename task
        if contains(rawtask, 'faces')
            bidstask = 'socialdoors';
        elseif contains(rawtask, 'doors')
            bidstask = 'doors';
        end
        
        inputname = sprintf('%s/sub-%d_ses-01_task-socialReward_%s_events.tsv', inputdir, subs(s), rawtask);
        
        % DEBUG: Show what we're looking for
        disp(['    Trying: ', inputname]);
        disp(['    Exists: ', num2str(isfile(inputname))]);
        
        if ~isfile(inputname)
            continue; % Skip to next iteration
        end
        
        sub_str = num2str(subs(s));
        bidsdir = fullfile(usedir, 'bids', ['sub-',sub_str], 'ses-01', 'func');
        bidsname = sprintf('%s/sub-%d_ses-01_task-%s_run-1_events.tsv', bidsdir, subs(s), bidstask);

        disp(['    Output will be: ', bidsname]);

        % Create directory and write file
        if ~exist(bidsdir, 'dir')
            mkdir(bidsdir);
        end
        
        T = readtable(inputname,'FileType','delimitedtext');
        writetable(T,bidsname,'FileType','text','Delimiter','\t')
        disp(['    Written successfully']);
    end
end
