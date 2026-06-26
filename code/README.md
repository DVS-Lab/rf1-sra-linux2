# Code Manual

This directory contains the active Linux2 pipeline, validation helpers, retained
configuration files, and historical compatibility scripts that still need human
review before any future deletion.

## Canonical Pipeline

| Order | Entry point | Worker/helper | Inputs | Outputs | Side effects |
|------:|-------------|---------------|--------|---------|--------------|
| 1 | `downloadXNAT.py` | XNAT Python client | Temple XNAT credentials | Raw DICOM folders under `SOURCEDATA_ROOT` | Downloads source data only. |
| 2 | `run_prepdata.sh` | `prepdata-linux2.sh`, `heuristics_rf1.py`, `heuristics_XA30.py`, `shiftdates.py` | Subject list, DICOMs | BIDS session, defaced T1w, shifted `scans.tsv`, optional MRIQC | Stages conversion in scratch; raw DICOMs remain untouched. |
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
| `run_prepdata.sh` | Production | Parallel BIDS conversion wrapper. | Operator | Bash, Python |
| `prepdata-linux2.sh` | Production | One subject/session HeuDiConv, deface, date shift, optional MRIQC. | `run_prepdata.sh` | Apptainer/Singularity, HeuDiConv, PyDeface, MRIQC |
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
| `check_fmriprep.sh` | Validation | Report incomplete fMRIPrep completion outputs. | Operator/tests | Bash, Python |
| `check_tedana.sh` | Validation | Report incomplete TEDANA completion outputs. | Operator/tests | Bash, Python |
| `check_mriqc.sh` | Validation | Report missing MRIQC subject folders. | Operator/tests | Bash |
| `check_pipeline_state.py` | Validation | Shared CLI for completion and path checks. | Shell scripts/tests | Python |
| `pipeline_utils.py` | Validation | Testable parsing, path, IntendedFor, and completion helpers. | Python scripts/tests | Python |
| `pipeline_common.sh` | Configuration | Shared Linux2 defaults and wrapper helpers. | Shell scripts | Bash |
| `print_subjects.py` | Helper | Normalize subject-list parsing for shell scripts. | `pipeline_common.sh` | Python |
| `downloadXNAT.py` | Production | Incremental XNAT download using prompted credentials. | Operator | Python, `xnat` |
| `downloadXNAT_mk.py` | Helper | XNAT download using alias/secret environment variables. | Operator | Python, `xnat` |
| `downloadXNAT_full.py` | Helper | Full project XNAT re-download. | Operator | Python, `xnat` |
| `heuristics_rf1.py` | Configuration | Pre-upgrade HeuDiConv heuristic. | `prepdata-linux2.sh` | HeuDiConv |
| `heuristics_XA30.py` | Configuration | XA30-era HeuDiConv heuristic. | `prepdata-linux2.sh` | HeuDiConv |
| `fmriprep_config.json`, `ses-01.json`, `ses-02.json` | Configuration | BIDS filter configuration. | fMRIPrep scripts | fMRIPrep |
| `fmriprep24.sh` | Historical compatibility | Older fMRIPrep 24 worker retained for review. | Not called by canonical wrapper | Singularity, fMRIPrep 24 |
| `fmriprep-warpkit.sh` | Historical compatibility | OpenNeuro smoke-test script for fMRIPrep Warpkit/MEDIC work. | Operator only | Singularity, fMRIPrep test image |
| `rsync_bids+warpkit_forhpc.sh` | Historical compatibility | Old HPC transfer helper retained pending review. | Not canonical | rsync |
| FLAIR/ICV scripts | Helper | One-off/anatomical QC helpers retained pending human review. | Operator only | FSL/Python as noted in scripts |
| `convert_SocialDoorsBids*.m` | Helper | MATLAB event conversion helpers. | Operator only | MATLAB |
| `rename_files.py`, `rename_studyID.py`, `diagnose_perFrameFunctionalGroupSeq.py` | Helper | Special-case source/metadata diagnosis and repair scripts. | Operator only | Python |

## Running Stages

All production wrappers accept `--dry-run` where practical and `--sublist FILE`
where they operate over a subject list. Subject lists allow blank lines,
comments, and either raw IDs or `sub-` prefixes.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash run_prepdata.sh --sublist sublist_new.txt --jobs 6 --dry-run
bash run_warpkit.sh --sublist sublist_new.txt --jobs 8 --dry-run
python3 addIntendedFor.py --bids-root ../bids --dry-run
bash run_fmriprep.sh --sublist sublist_new.txt --jobs 2 --dry-run
bash run_tedana.sh --sublist sublist_all.txt --jobs 8 --dry-run
python3 genTedanaConfounds.py --dry-run
bash run_mriqc.sh --sublist sublist_all.txt --jobs 10 --dry-run
python3 extract-metrics.py --sublist sublist_all.txt --dry-run
```

Use `--overwrite` only when replacing valid existing outputs is intentional.
`prepdata-linux2.sh` moves existing BIDS session output to a timestamped backup
after a new staged conversion has succeeded. `warpkit.sh` deletes only explicit
generated fieldmap outputs when `--overwrite` is supplied.

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
3. Create a separate scratch test workspace and set `code/config.env` to point there.
4. Record the branch commit SHA and container versions.
5. Select a minimal representative set: one pre-upgrade ses-01 case, one post-upgrade ses-01 case, one ses-02 subject, and one intentionally absent task/run when available.
6. Run every stage first with `--dry-run` or validation mode.
7. Run actual processing only in the scratch workspace.
8. Compare outputs with trusted production outputs when available.
9. Record every command, exit code, and unexpected warning.
10. Confirm raw DICOM source data were not changed.
11. Confirm no existing production BIDS or derivatives were removed.
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

## Needs Human Decision

The following are intentionally preserved pending review:

| Item | Reason |
| --- | --- |
| `derivatives/flirt/check-wm-mask.sh`, `derivatives/flirt/voxel-count-L1.sh` | Scripts live under a generated-output directory and use hard-coded FLIRT paths, but may encode a still-needed anatomical QC workflow. |
| `fmriprep24.sh` | Not part of the canonical fMRIPrep 25 workflow, but may be needed to reproduce old comparisons. |
| FLAIR/ICV helper scripts and subject-list variants | They may reflect analysis-specific cohorts or acquisition exceptions. |
| Scanner cutoff date | Code uses March 4, 2025; comments historically said March 18, 2025. |
