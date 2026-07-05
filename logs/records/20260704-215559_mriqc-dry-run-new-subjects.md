# Run Record: mriqc-dry-run-new-subjects

- Timestamp: 20260704-215559
- Branch: codex/repo-cleanup-validation
- Commit: 5f45284
- Host: CLA19787.tu.temple.edu
- User: tug87422
- Working directory: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code`
- Raw log: `/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/logs/runs/20260704-215559_mriqc-dry-run-new-subjects.log`
- Command exit: 0
- Check exit: none
- Summary: COMMAND COMPLETED: no check command provided.

## Command

```bash
bash run_mriqc.sh --sublist ../logs/runlists/prepdata-new-20260704.txt --jobs 2 --dry-run
```

## Full Log

```text
RUN START: 20260704-215559
PROJECT_ROOT: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test
GIT: codex/repo-cleanup-validation 5f45284
HOST: CLA19787.tu.temple.edu
USER: tug87422
PWD: /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/code
COMMAND: bash run_mriqc.sh --sublist ../logs/runlists/prepdata-new-20260704.txt --jobs 2 --dry-run

Using subject list: ../logs/runlists/prepdata-new-20260704.txt
Launching MRIQC sub-11923 ses-01
Launching MRIQC sub-11923 ses-02
MRIQC command: singularity run --cleanenv -B /ZPOOL/data/tools/templateflow:/opt/templateflow -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/bids:/data -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc:/out -B /ZPOOL/data/scratch/tug87422:/scratch /ZPOOL/data/tools/mriqc-24.0.2.simg /data /out participant --participant_label 11923 --session-id 01 --modalities bold --no-sub -w /scratch
Dry run: not launching MRIQC.
No BIDS data for optional sub-11923 ses-02; skipping MRIQC.
Launching MRIQC sub-11924 ses-01
Launching MRIQC sub-11924 ses-02
MRIQC command: singularity run --cleanenv -B /ZPOOL/data/tools/templateflow:/opt/templateflow -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/bids:/data -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc:/out -B /ZPOOL/data/scratch/tug87422:/scratch /ZPOOL/data/tools/mriqc-24.0.2.simg /data /out participant --participant_label 11924 --session-id 01 --modalities bold --no-sub -w /scratch
Dry run: not launching MRIQC.
No BIDS data for optional sub-11924 ses-02; skipping MRIQC.
Launching MRIQC sub-11928 ses-01
Launching MRIQC sub-11928 ses-02
MRIQC command: singularity run --cleanenv -B /ZPOOL/data/tools/templateflow:/opt/templateflow -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/bids:/data -B /ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test/derivatives/mriqc:/out -B /ZPOOL/data/scratch/tug87422:/scratch /ZPOOL/data/tools/mriqc-24.0.2.simg /data /out participant --participant_label 11928 --session-id 01 --modalities bold --no-sub -w /scratch
Dry run: not launching MRIQC.
No BIDS data for optional sub-11928 ses-02; skipping MRIQC.

COMMAND EXIT: 0
```
