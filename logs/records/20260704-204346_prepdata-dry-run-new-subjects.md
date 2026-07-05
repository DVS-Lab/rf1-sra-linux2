# Run Record: prepdata-dry-run-new-subjects

- Timestamp: 20260704-204346
- Branch: codex/repo-cleanup-validation
- Commit: 5f45284
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/logs/runs/20260704-204346_prepdata-dry-run-new-subjects.log`
- Command exit: 0
- Check exit: none
- Summary: COMMAND COMPLETED: no check command provided.

## Command

```bash
bash run_prepdata.sh --sublist ../logs/runlists/prepdata-new-20260704.txt --jobs 2 --dry-run
```

## Full Log

```text
RUN START: 20260704-204346
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test
GIT: codex/repo-cleanup-validation 5f45284
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code
COMMAND: bash run_prepdata.sh --sublist ../logs/runlists/prepdata-new-20260704.txt --jobs 2 --dry-run

Using subject list: ../logs/runlists/prepdata-new-20260704.txt
Launching prepdata sub-11923 ses-01
Launching prepdata sub-11923 ses-02
No source directory for optional sub-11923 ses-02; skipping.
Launching prepdata sub-11924 ses-01
Heuristic chosen for sub-11923 ses-01: heuristics_XA30.py [seen=2026-06-11 19:27:10; cutoff=2025-03-04]
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11923-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11923 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Launching prepdata sub-11924 ses-02
No source directory for optional sub-11924 ses-02; skipping.
Heuristic chosen for sub-11924 ses-01: heuristics_XA30.py [seen=2026-04-21 20:49:20; cutoff=2025-03-04]
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11924-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11924 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.
Launching prepdata sub-11928 ses-01
Launching prepdata sub-11928 ses-02
No source directory for optional sub-11928 ses-02; skipping.
Heuristic chosen for sub-11928 ses-01: heuristics_XA30.py [seen=2026-06-03 09:54:40; cutoff=2025-03-04]
HeuDiConv command: apptainer run --cleanenv -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test:/project -B /ZPOOL/data/scratch/tug87422/prepdata-sub-11928-ses-01.DRYRUN:/out -B /ZPOOL/data/sourcedata/sourcedata/rf1-sra:/sourcedata /ZPOOL/data/tools/heudiconv-1.4.0.sif -d /sourcedata/Smith-SRA-\{subject\}/Smith-SRA-\{subject\}/scans/\*/\*/DICOM/files/\*.dcm -o /out/bids/ -f /project/code/heuristics_XA30.py -s 11928 -ss 01 -c dcm2niix -b --minmeta --overwrite
Dry run: not converting, defacing, or shifting dates.

COMMAND EXIT: 0
```
