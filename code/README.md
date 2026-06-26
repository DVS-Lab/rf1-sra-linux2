# Code Manual

All repository scripts live in this directory. Routine batch processing should
not require editing scripts: update `sublist-new.txt`, then run the standard
stage commands below.

## Canonical Pipeline

| Order | Entry point | Worker/helper | Inputs | Outputs | Side effects |
|------:|-------------|---------------|--------|---------|--------------|
| 1 | `downloadXNAT.py` | XNAT Python client | Temple XNAT credentials | Raw DICOM folders under `/ZPOOL/data/sourcedata/sourcedata/rf1-sra` | Downloads source data only. |
| 2 | `run_prepdata.sh` | `prepdata.sh`, `heuristics_rf1.py`, `heuristics_XA30.py`, `shiftdates.py` | `sublist-new.txt`, DICOMs | BIDS session, defaced T1w, shifted `scans.tsv`, optional MRIQC | Stages conversion in scratch; raw DICOMs remain untouched. |
| 3 | `run_warpkit.sh` | `warpkit.sh` | BIDS multi-echo mag/phase files and JSON | BIDS `fmap/` fieldmap and magnitude files | Removes only explicit generated fmap files when `--overwrite` is used. |
| 4 | `addIntendedFor.py` | `pipeline_utils.py` | BIDS `fmap/*.json`, existing BOLD files | Updated fieldmap JSON | Atomic writes; `--dry-run` available. |
| 5 | `run_fmriprep.sh` | `fmriprep.sh`, `fmriprep_config.json` | BIDS data | `derivatives/fmriprep` | Skips only when practical completion outputs exist. |
| 6 | `run_tedana.sh` | `tedana.sh` | fMRIPrep echo outputs, BIDS echo metadata | `derivatives/tedana` | Logs missing optional runs under `logs/`. |
| 7 | `genTedanaConfounds.py` | pandas | fMRIPrep confounds, TEDANA mixing/metrics | `derivatives/fsl/confounds_tedana` | Atomic TSV writes; row-count validation. |
| 8 | `run_mriqc.sh` | `mriqc.sh` | BIDS data | `derivatives/mriqc` | Container run only; no raw-source edits. |
| 9 | `extract-metrics.py` | MRIQC JSON outputs | MRIQC participant JSON | CSV metrics table | Atomic CSV write. |

## Script Index

| Script | Status | Purpose | Called by | Required software |
|--------|--------|---------|-----------|-------------------|
| `sublist-new.txt` | Batch input | Current batch subject list. This is the normal per-batch edit point. | All wrappers by default | Text editor |
| `run_prepdata.sh` | Production | Parallel BIDS conversion wrapper. | Operator | Bash, Python |
| `prepdata.sh` | Production | One subject/session HeuDiConv, deface, date shift, optional MRIQC. | `run_prepdata.sh` | Apptainer/Singularity, HeuDiConv, PyDeface, MRIQC |
| `run_warpkit.sh` | Production | Parallel Warpkit wrapper. | Operator | Bash, Python |
| `warpkit.sh` | Production | One subject/session/task/run Warpkit fieldmap generation. | `run_warpkit.sh` | Singularity, Warpkit, FSL |
| `addIntendedFor.py` | Production | Add/repair fieldmap `IntendedFor` entries that point to existing BOLD files. | Operator | Python |
| `run_fmriprep.sh` | Production | Parallel fMRIPrep wrapper. | Operator | Bash, Python |
| `fmriprep.sh` | Production | One-subject fMRIPrep run. | `run_fmriprep.sh`, `submit_fmriprep.sh` | Singularity, fMRIPrep |
| `run_tedana.sh` | Production | Parallel TEDANA wrapper. | Operator | Bash, Python |
| `tedana.sh` | Production | One-subject TEDANA run across sessions/tasks/runs. | `run_tedana.sh` | TEDANA, Python |
| `genTedanaConfounds.py` | Production | Build FSL-ready confound tables. | Operator | Python, pandas |
| `run_mriqc.sh` | Production | Parallel MRIQC wrapper. | Operator | Bash |
| `mriqc.sh` | Production | One subject/session MRIQC run. | `run_mriqc.sh`, optional prepdata stage | Singularity, MRIQC |
| `extract-metrics.py` | Helper | Extract MRIQC `fd_mean` and `tsnr`. | Operator | Python |
| `submit_fmriprep.sh` | Helper | Backward-compatible launcher for `run_fmriprep.sh`. | Operator | Bash |
| `check_fmriprep.sh` | Validation | Report incomplete fMRIPrep completion outputs. | Operator/tests | Bash, Python |
| `check_tedana.sh` | Validation | Report incomplete TEDANA completion outputs. | Operator/tests | Bash, Python |
| `check_mriqc.sh` | Validation | Report missing MRIQC subject folders. | Operator/tests | Bash |
| `check_pipeline_state.py` | Validation | Shared CLI for completion and path checks. | Shell scripts/tests | Python |
| `check_shell_syntax.sh` | Validation | Shell syntax and optional ShellCheck lint. | `make test` | Bash, ShellCheck optional |
| `validate_repo.py` | Validation | JSON, README path, and repository hygiene checks. | `make test` | Python |
| `pipeline_utils.py` | Validation | Testable parsing, path, IntendedFor, and completion helpers. | Python scripts/tests | Python |
| `pipeline_common.sh` | Shared constants | Fixed Linux2 source/tool paths plus checkout-relative project outputs. | Shell scripts | Bash |
| `print_subjects.py` | Helper | Normalize subject-list parsing for shell scripts. | `pipeline_common.sh` | Python |
| `downloadXNAT.py` | Production | Incremental XNAT download using prompted credentials. | Operator | Python, `xnat` |
| `heuristics_rf1.py` | Configuration | Pre-upgrade HeuDiConv heuristic. | `prepdata.sh` | HeuDiConv |
| `heuristics_XA30.py` | Configuration | XA30-era HeuDiConv heuristic. | `prepdata.sh` | HeuDiConv |
| `fmriprep_config.json` | Configuration | fMRIPrep BIDS filter configuration for multi-session runs; keeps functional inputs to magnitude images. | `fmriprep.sh` | fMRIPrep |
| `convert_SocialDoorsBids.m` | Helper | MATLAB event converter for Social Doors/Doors that reads `sublist-new.txt` and handles both sessions. | Operator only | MATLAB |
| FLAIR/anatomical QC helpers | Helper | Optional anatomical QC checks kept in `code/`: `bet-flair.sh`, `bet-flair-coverage.sh`, `check-wm-mask.sh`, `create-T2.sh`, `extract_icv_fmriprep.py`, `flair-metrics.sh`, `flair-outliers.sh`, `flair_to_mni_flirt.py`, `voxel-count-L1.sh`. | Operator only | FSL/Python as noted in scripts |

## Batch Operation

For each new batch, edit only:

```bash
code/sublist-new.txt
```

The file contains one subject per line. Blank lines and comments beginning with
`#` are ignored, and either `10001` or `sub-10001` forms are accepted.

The standard stage commands use `sublist-new.txt` by default:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash run_prepdata.sh --dry-run
bash run_warpkit.sh --dry-run
python3 addIntendedFor.py --dry-run
bash run_fmriprep.sh --dry-run
bash run_tedana.sh --dry-run
python3 genTedanaConfounds.py --dry-run
bash run_mriqc.sh --dry-run
python3 extract-metrics.py --dry-run
```

Remove `--dry-run` after reviewing the planned commands. Use `--sublist FILE`
only for an exceptional review or recovery run.

## Linux2 Paths

The pipeline assumes the standard Smith Lab Linux2 source-data and tool layout.
Operators should not edit paths for routine runs. The project root is derived
from the checkout location, which allows a separate validation clone such as
`/ZPOOL/data/projects/rf1-sra-linux2-jacob` to write to its own `bids/`,
`derivatives/`, and `logs/` directories while reading the same source DICOMs
and containers.

| Item | Path |
| --- | --- |
| Production checkout | `/ZPOOL/data/projects/rf1-sra-linux2` |
| Example validation checkout | `/ZPOOL/data/projects/rf1-sra-linux2-jacob` |
| Source DICOMs | `/ZPOOL/data/sourcedata/sourcedata/rf1-sra` |
| Scratch | `/ZPOOL/data/scratch` |
| Tool/container directory | `/ZPOOL/data/tools` |
| HeuDiConv | `/ZPOOL/data/tools/heudiconv_1.3.3.sif` |
| MRIQC | `/ZPOOL/data/tools/mriqc-24.0.2.simg` |
| fMRIPrep | `/ZPOOL/data/tools/fmriprep-25.2.5.simg` |
| Warpkit | `/ZPOOL/data/tools/warpkit.sif` |
| TemplateFlow | `/ZPOOL/data/tools/templateflow` |
| FreeSurfer license | `/ZPOOL/data/tools/licenses/fs_license.txt` |

## Overwrite Behavior

Use `--overwrite` only when replacing valid existing outputs is intentional.
`prepdata.sh` runs HeuDiConv in scratch first and checks that the staged BIDS
session exists. Only after that check passes does it remove the existing live
BIDS session and move the staged session into place. This keeps failed
conversion attempts from destroying the last valid copy while also keeping the
live `bids/` tree free of non-BIDS backup folders.

`warpkit.sh` deletes only explicit generated fieldmap outputs when
`--overwrite` is supplied.

## Expected Outputs

Predata/HeuDiConv should create `bids/sub-<id>/ses-<ses>/`, BIDS metadata,
expected multi-echo task files, a defaced T1w when T1w exists, and shifted
`scans.tsv`. It must not alter raw DICOM source data.

Warpkit requires all four magnitude NIfTIs, phase NIfTIs, and phase JSON files
before launch. It writes fieldmap/magnitude NIfTIs and JSON files under the BIDS
session `fmap/` directory and a completion marker under `derivatives/warpkit`.

`addIntendedFor.py` updates only fieldmap/magnitude JSONs, keeps targets within
the same subject/session, includes only existing magnitude BOLD files, writes
atomically, and is idempotent.

fMRIPrep completion checks look for the subject HTML report plus expected
per-run preprocessed echo and confounds files. TEDANA completion checks look for
denoised BOLD, mixing matrix, and metrics files. These checks are operational
completion checks, not scientific validation.

## Tests

From the repository root:

```bash
make test
```

The tests cover subject-list parsing, session/task/run selection, scanner
heuristic selection around the preserved March 4 cutoff, IntendedFor generation
for present/missing runs, atomic metadata writes, unsafe path refusal, Warpkit
input manifests, and fMRIPrep/TEDANA completion checks.

## Jacob's Linux2 Validation Checklist

Before this branch can merge, Jacob should:

1. Clone or switch to `codex/repo-cleanup-validation` on Linux2.
2. Confirm the production `main` checkout remains untouched.
3. Create a separate scratch test workspace.
4. Record the branch commit SHA and container versions.
5. Select a minimal representative set: one pre-upgrade ses-01 case, one post-upgrade ses-01 case, one ses-02 subject, and one intentionally absent task/run when available.
6. Run every stage first with `--dry-run` or validation mode.
7. Run actual processing only in the scratch workspace.
8. Compare outputs with trusted production outputs when available.
9. Record every command, exit code, and unexpected warning.
10. Confirm raw DICOM source data were not changed.
11. Confirm no existing production BIDS or derivatives were removed except where `--overwrite` was intentionally used.
12. Run the BIDS validator after conversion and fieldmap metadata changes.
13. Verify expected subject/session/task/run coverage.
14. Confirm all `IntendedFor` paths resolve to existing BOLD files.
15. Confirm fieldmap units and metadata.
16. Confirm fMRIPrep reports and expected session-level outputs.
17. Confirm TEDANA denoised outputs, mixing matrices, and metrics files.
18. Confirm confound row counts match the corresponding BOLD time series.
19. Confirm MRIQC outputs and metric extraction.
20. Run `make test`.
21. Leave a PR comment with the commit SHA tested, subjects/sessions tested, stages tested, pass/fail result, discrepancies, and merge/request-changes recommendation.

The branch should remain draft until this checklist is complete and David
approves the pull request.

## Still To Confirm

The scanner-upgrade cutoff needs Linux2 confirmation. The code has used
March 4, 2025; comments historically said March 18, 2025. This branch preserves
the March 4 behavior until Jacob confirms otherwise.
