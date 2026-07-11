# Code Manual

All repository scripts live in this directory. Routine batch processing should
not require editing scripts: update `sublist-new.txt`, then run the standard
stage commands below.

## Upstream/Downstream Boundary

`rf1-sra-linux2` runs before `rf1-dwi`. This repository owns the shared RF1-SRA
BIDS dataset plus fMRIPrep, FreeSurfer, CIFTI, TEDANA, MRIQC, confound
derivatives, and cohort-level metric summaries. The DWI repository should
consume those validated outputs for QSIPrep/QSIRecon instead of copying or
regenerating them.

The dependency map is:

```text
Raw DICOMs / XNAT
  -> rf1-sra-linux2 BIDS conversion
  -> rf1-sra-linux2 Warpkit / IntendedFor
  -> rf1-sra-linux2 fMRIPrep / FreeSurfer / CIFTI
  -> rf1-sra-linux2 TEDANA / MRIQC / confounds
  -> rf1-sra-linux2 cohort-level MRIQC metrics and outlier review
  -> rf1-dwi QSIPrep / QSIRecon
```

Downstream paths should point at the production Linux2 checkout:
`/ZPOOL/data/projects/rf1-sra-linux2`. Historical validation checkout names are
documented in `docs/archive/validation-history.md`, but they are not production
defaults. Scripts in this repo derive
`PROJECT_ROOT` from the checkout location so an intentional validation clone
can still write to its own `bids/`, `derivatives/`, and `logs/` trees.

## Canonical Pipeline

| Order | Entry point | Worker/helper | Inputs | Outputs | Side effects |
|------:|-------------|---------------|--------|---------|--------------|
| 1 | `downloadXNAT.py` | XNAT Python client | Temple XNAT credentials | Raw DICOM folders under `/ZPOOL/data/sourcedata/sourcedata/rf1-sra` | Downloads source data only. |
| 2 | `run_prepdata.sh` | `prepdata.sh`, `heuristics_rf1.py`, `heuristics_XA30.py`, `shiftdates.py` | `sublist-new.txt`, DICOMs | BIDS session, defaced T1w, shifted `scans.tsv` | Stages conversion in scratch; raw DICOMs remain untouched. Check with `check_bids.sh`. |
| 3 | `run_warpkit.sh` | `warpkit.sh` | BIDS multi-echo mag/phase files and JSON | BIDS `fmap/` fieldmap and magnitude files | Removes only explicit generated fmap files when `--overwrite` is used. Check with `check_warpkit.sh`. |
| 4 | `addIntendedFor.py` | `pipeline_utils.py` | BIDS `fmap/*.json`, existing BOLD files | Updated fieldmap JSON | Atomic writes; `--dry-run` available. |
| 5 | `run_fmriprep.sh` | `fmriprep.sh`, `fmriprep_config.json` | BIDS data | `derivatives/fmriprep`, `derivatives/freesurfer` | Generates volumetric, fsLR CIFTI, and FreeSurfer outputs; skips only when practical completion outputs exist. |
| 6 | `run_tedana.sh` | `tedana.sh` | fMRIPrep echo outputs, BIDS echo metadata | `derivatives/tedana` | Logs missing optional runs under `logs/`. |
| 7 | `genTedanaConfounds.py` | pandas | fMRIPrep confounds, TEDANA mixing/metrics | `derivatives/fsl/confounds_tedana` | Atomic TSV writes; row-count validation. |
| 8 | `run_mriqc.sh` | `mriqc.sh` | BIDS data | `derivatives/mriqc` | Container run only; no raw-source edits. |
| 9 | `mriqc_group.sh` | MRIQC container | Completed participant MRIQC outputs | MRIQC group report | Cohort-level step; run after the full participant batch completes. |
| 10 | `extract-metrics.py` | MRIQC JSON outputs | Completed cohort MRIQC participant JSON | CSV metrics table | Cohort-level helper; atomic CSV write. |

`make_repair_runlists.py` is the filesystem audit helper for recovery runs. It
does not launch processing; it writes targeted runlists and a missing-path TSV
under `logs/runlists/`.

## Script Reference

Each entry uses the same fields so operators can scan quickly.

### `sublist-new.txt`
- Status: Batch input.
- Purpose: Current fMRI/data-management production batch list.
- Inputs: One subject per line, with comments and blank lines allowed.
- Outputs: None.
- Typical command: edit with a text editor before a new batch.
- Checker: Parsed by each wrapper and checker.
- Notes: This is the normal per-batch edit point.

### `run_logged.sh`
- Status: Logging helper.
- Purpose: Run a command and optional checker with one raw log and one compact run record.
- Inputs: A command after `--`, and optionally a checker after `--check`.
- Outputs: Ignored `logs/runs/*.log` plus tracked `logs/records/*.md`.
- Typical command: `bash run_logged.sh --label fmriprep-check -- bash check_fmriprep.sh --sublist "$SUBLIST"`.
- Checker: The optional command supplied after `--check`.
- Notes: Use separate run and check records for long production stages when readability matters.

### `make_repair_runlists.py`
- Status: Recovery helper.
- Purpose: Inspect the live filesystem and create subject lists for incomplete BIDS, MRIQC, WarpKit, IntendedFor, and fMRIPrep stages.
- Inputs: A subject list, the project BIDS/derivatives tree, and source DICOM root.
- Outputs: `logs/runlists/*_*-repair.txt`, `*_fmriprep-ready.txt`, `*_fmriprep-incomplete.txt`, and `*_missing-paths.tsv`.
- Typical command: `python3 make_repair_runlists.py --sublist "$SUBLIST" --prefix repair-$(date +%Y%m%d)`.
- Checker: Review the missing-path TSV and rerun the relevant stage checkers after repair runs.
- Notes: `fmriprep-ready` excludes subjects with BIDS/WarpKit/IntendedFor prerequisite issues; MRIQC is tracked separately because it is QC, not an fMRIPrep prerequisite.

### `downloadXNAT.py`
- Status: Production input helper.
- Purpose: Incrementally download source DICOMs from Temple XNAT.
- Inputs: XNAT credentials and the configured RF1-SRA source-data destination.
- Outputs: Raw DICOM folders under `/ZPOOL/data/sourcedata/sourcedata/rf1-sra`.
- Typical command: run `downloadXNAT.py` with Python 3.
- Checker: Confirm expected subject folders exist before conversion.
- Notes: Downloads source data only; preprocessing scripts treat source data as immutable.

### `run_prepdata.sh`
- Status: Production wrapper.
- Purpose: Launch BIDS conversion for every listed subject and session.
- Inputs: `sublist-new.txt`, raw DICOM source data, and `prepdata.sh`.
- Outputs: BIDS sessions, defaced T1w images, and shifted `scans.tsv` files.
- Typical command: `bash run_prepdata.sh --sublist "$SUBLIST" --jobs 6`.
- Checker: `bash check_bids.sh --sublist "$SUBLIST"`.
- Notes: Prints the subject list and job plan before launching.

### `prepdata.sh`
- Status: Production worker.
- Purpose: Run one subject/session through HeuDiConv, defacing, and date shifting.
- Inputs: One subject, one session, DICOMs, HeuDiConv image, heuristics, and `shiftdates.py`.
- Outputs: One staged and then live BIDS subject/session tree.
- Typical command: normally called by `run_prepdata.sh`.
- Checker: `check_bids.sh`.
- Notes: Stages in scratch before replacing live BIDS outputs; `--overwrite` is required for replacement. Raw localizer and PhoenixZIPReport series remain in sourcedata, but HeuDiConv filters them during indexing because they are scanner-generated non-BIDS series that can trigger enhanced-DICOM parsing failures.

### `heuristics_rf1.py`
- Status: HeuDiConv configuration.
- Purpose: Classify pre-upgrade RF1-SRA sequences for BIDS conversion.
- Inputs: HeuDiConv sequence metadata.
- Outputs: BIDS key assignments.
- Typical command: not run directly.
- Checker: Conversion output plus tests around heuristic selection.
- Notes: Includes the same conservative filename filter as `heuristics_XA30.py`: localizer and PhoenixZIPReport scan directories are excluded before DICOM parsing, without modifying raw source data.

### `heuristics_XA30.py`
- Status: HeuDiConv configuration.
- Purpose: Classify XA30-era RF1-SRA sequences for BIDS conversion.
- Inputs: HeuDiConv sequence metadata.
- Outputs: BIDS key assignments.
- Typical command: not run directly.
- Checker: Conversion output plus tests around heuristic selection.
- Notes: The March 4, 2025 cutoff remains the current production behavior. Uses the same localizer/PhoenixZIPReport filename filter as `heuristics_rf1.py`.

### `shiftdates.py`
- Status: Production helper.
- Purpose: Shift BIDS dates after conversion.
- Inputs: Generated BIDS metadata and scan files.
- Outputs: Updated date fields and `scans.tsv` files.
- Typical command: normally called by `prepdata.sh`.
- Checker: `check_bids.sh`.
- Notes: Keeps raw DICOM source data untouched.

### `run_warpkit.sh`
- Status: Production wrapper.
- Purpose: Launch Warpkit fieldmap generation across expected subject/session/task/run inputs.
- Inputs: BIDS multi-echo magnitude/phase files and `warpkit.sh`.
- Outputs: BIDS `fmap/` products plus Warpkit completion markers.
- Typical command: `bash run_warpkit.sh --sublist "$SUBLIST" --jobs 8`.
- Checker: `bash check_warpkit.sh --sublist "$SUBLIST"`.
- Notes: Uses native `wk-medic` from `PATH` by default. Install it with `python -m pip install warpkit` in a Python >=3.11 environment. Set `WARPKIT_BACKEND=apptainer` only to use the legacy container fallback. Set `WARPKIT_N_CPUS`, `OMP_THREADS`, `JULIA_NUM_THREADS`, or `JULIA_NUM_GC_THREADS` to tune per-run concurrency.

### `warpkit.sh`
- Status: Production worker.
- Purpose: Generate fieldmap and magnitude products for one subject/session/task/run.
- Inputs: Four magnitude images, phase images, phase JSON files, Warpkit, and FSL.
- Outputs: BIDS `fmap/*` NIfTI/JSON files and `derivatives/warpkit` markers.
- Typical command: normally called by `run_warpkit.sh`.
- Checker: `check_warpkit.sh`.
- Notes: `--overwrite` deletes only explicit generated fieldmap and Warpkit derivative products. The worker supports default `WARPKIT_BACKEND=native` and fallback `WARPKIT_BACKEND=apptainer`, passes `WARPKIT_N_CPUS` through to WarpKit, and logs the backend/thread plan.

### `addIntendedFor.py`
- Status: Production metadata helper.
- Purpose: Add or repair BIDS fieldmap `IntendedFor` entries.
- Inputs: BIDS fieldmap JSON files and existing BOLD files.
- Outputs: Updated fieldmap JSON files.
- Typical command: `python3 addIntendedFor.py --sublist "$SUBLIST"`.
- Checker: BIDS validation plus `check_warpkit.sh` context.
- Notes: Supports `--dry-run`, writes atomically, and is idempotent.

### `run_mriqc.sh`
- Status: Production wrapper.
- Purpose: Launch participant-level MRIQC across listed subjects/sessions.
- Inputs: BIDS data and `mriqc.sh`.
- Outputs: Participant-level MRIQC derivatives.
- Typical command: `bash run_mriqc.sh --sublist "$SUBLIST" --jobs 8`.
- Checker: `bash check_mriqc.sh --sublist "$SUBLIST"`.
- Notes: MRIQC is restartable and does not require reconverting BIDS.

### `mriqc.sh`
- Status: Production worker.
- Purpose: Run one subject/session through MRIQC.
- Inputs: BIDS data, MRIQC container, TemplateFlow, and scratch.
- Outputs: `derivatives/mriqc` participant reports and JSON files.
- Typical command: normally called by `run_mriqc.sh`.
- Checker: `check_mriqc.sh`.
- Notes: Participant MRIQC should complete before cohort-level group MRIQC.

### `mriqc_group.sh`
- Status: Cohort-level production step.
- Purpose: Run the MRIQC group report after participant MRIQC is complete.
- Inputs: Completed participant-level MRIQC outputs.
- Outputs: MRIQC group report under `derivatives/mriqc`.
- Typical command: run `mriqc_group.sh` with Bash.
- Checker: Inspect group report and cohort QC outputs.
- Notes: Run with full-batch/cohort review, not during routine new-subject validation.

### `extract-metrics.py`
- Status: Cohort-level QC helper.
- Purpose: Extract MRIQC `fd_mean` and `tsnr` values for run/subject review.
- Inputs: Completed MRIQC participant JSON files and a full-batch subject list.
- Outputs: CSV metric summaries.
- Typical command: `python3 extract-metrics.py --sublist "$SUBLIST"`.
- Checker: Review generated CSVs with group MRIQC.
- Notes: Use after a full batch, not as a per-new-subject gate.

### `run_fmriprep.sh`
- Status: Production wrapper.
- Purpose: Launch fMRIPrep across listed subjects.
- Inputs: BIDS data, `fmriprep.sh`, fMRIPrep config, TemplateFlow, and FreeSurfer license.
- Outputs: `derivatives/fmriprep` and `derivatives/freesurfer`.
- Typical command: `bash run_fmriprep.sh --sublist "$SUBLIST" --jobs 2`.
- Checker: `bash check_fmriprep.sh --sublist "$SUBLIST"`.
- Notes: Splits 96 CPU threads and 196000 MB RAM across simultaneous subjects.

### `fmriprep.sh`
- Status: Production worker.
- Purpose: Run one subject through fMRIPrep with FreeSurfer and fsLR CIFTI outputs.
- Inputs: BIDS data, fMRIPrep container, `fmriprep_config.json`, TemplateFlow, and license.
- Outputs: Subject HTML, volumetric outputs, CIFTI dtseries, and FreeSurfer subject.
- Typical command: normally called by `run_fmriprep.sh`.
- Checker: `check_fmriprep.sh`.
- Notes: Generates the upstream anatomy derivatives consumed by `rf1-dwi`.

### `fmriprep_config.json`
- Status: fMRIPrep configuration.
- Purpose: Filter multi-session fMRIPrep inputs for this dataset.
- Inputs: BIDS dataset metadata.
- Outputs: fMRIPrep BIDS filter settings.
- Typical command: not run directly.
- Checker: `check_fmriprep.sh` plus fMRIPrep reports.
- Notes: Keeps functional inputs to magnitude images.

### `submit_fmriprep.sh`
- Status: Compatibility helper.
- Purpose: Preserve an older launcher name for fMRIPrep work.
- Inputs: Same as `run_fmriprep.sh`.
- Outputs: Same as `run_fmriprep.sh`.
- Typical command: prefer `bash run_fmriprep.sh --sublist "$SUBLIST" --jobs 2`.
- Checker: `check_fmriprep.sh`.
- Notes: New production docs should point at `run_fmriprep.sh`.

### `run_tedana.sh`
- Status: Production wrapper.
- Purpose: Launch TEDANA across listed subjects.
- Inputs: BIDS echo metadata, fMRIPrep echo outputs, and `tedana.sh`.
- Outputs: `derivatives/tedana`.
- Typical command: `bash run_tedana.sh --sublist "$SUBLIST" --jobs 8`.
- Checker: `bash check_tedana.sh --sublist "$SUBLIST"`.
- Notes: Prints the subject list and job plan before launching.

### `tedana.sh`
- Status: Production worker.
- Purpose: Run TEDANA for available task/runs for one subject.
- Inputs: fMRIPrep echo outputs and BIDS echo metadata.
- Outputs: Denoised BOLD, mixing matrix, and component metrics.
- Typical command: normally called by `run_tedana.sh`.
- Checker: `check_tedana.sh`.
- Notes: Missing optional runs are logged and skipped when no BIDS echo input exists.

### `genTedanaConfounds.py`
- Status: Production helper.
- Purpose: Build FSL-ready confound TSVs from TEDANA and fMRIPrep outputs.
- Inputs: fMRIPrep confounds, TEDANA mixing matrices, TEDANA metrics, and subject list.
- Outputs: `derivatives/fsl/confounds_tedana`.
- Typical command: `python3 genTedanaConfounds.py --sublist "$SUBLIST"`.
- Checker: Row-count validation inside the script and downstream FSL model review.
- Notes: Writes atomically.

### `check_bids.sh`
- Status: Checker.
- Purpose: Report missing BIDS/prepdata outputs and unshifted `scans.tsv` files.
- Inputs: Subject list and BIDS tree.
- Outputs: Terminal pass/fail summary.
- Typical command: `bash check_bids.sh --sublist "$SUBLIST"`.
- Checker: Ends with `CHECK PASSED` or `CHECK FAILED`.
- Notes: Suitable for `run_logged.sh` records.

### `check_warpkit.sh`
- Status: Checker.
- Purpose: Report missing Warpkit inputs or generated fieldmap outputs.
- Inputs: Subject list, BIDS tree, and Warpkit derivatives.
- Outputs: Terminal pass/fail summary.
- Typical command: `bash check_warpkit.sh --sublist "$SUBLIST"`.
- Checker: Ends with `CHECK PASSED` or `CHECK FAILED`.
- Notes: Fails only when expected outputs are missing for available inputs.

### `check_mriqc.sh`
- Status: Checker.
- Purpose: Report missing MRIQC JSON outputs for BIDS BOLD inputs.
- Inputs: Subject list, BIDS tree, and MRIQC derivatives.
- Outputs: Terminal pass/fail summary.
- Typical command: `bash check_mriqc.sh --sublist "$SUBLIST"`.
- Checker: Ends with `CHECK PASSED` or `CHECK FAILED`.
- Notes: Participant-level only; group MRIQC is a separate cohort step.

### `check_fmriprep.sh`
- Status: Checker.
- Purpose: Report incomplete fMRIPrep, FreeSurfer, and CIFTI completion outputs.
- Inputs: Subject list, BIDS tree, fMRIPrep derivatives, and FreeSurfer subjects.
- Outputs: Terminal pass/fail summary.
- Typical command: `bash check_fmriprep.sh --sublist "$SUBLIST"`.
- Checker: Ends with `CHECK PASSED` or `CHECK FAILED`.
- Notes: Operational completion check, not scientific image review.

### `check_tedana.sh`
- Status: Checker.
- Purpose: Report incomplete TEDANA denoised outputs, mixing matrices, and metrics.
- Inputs: Subject list, BIDS echo inputs, and TEDANA derivatives.
- Outputs: Terminal pass/fail summary.
- Typical command: `bash check_tedana.sh --sublist "$SUBLIST"`.
- Checker: Ends with `CHECK PASSED` or `CHECK FAILED`.
- Notes: Skips task/runs without BIDS echo input.

### `check_pipeline_state.py`
- Status: Shared checker implementation.
- Purpose: Provide testable completion and path checks for shell wrappers.
- Inputs: CLI options from `check_*.sh`.
- Outputs: Detailed pass/fail diagnostics.
- Typical command: called by checker scripts.
- Checker: Covered by `make test`.
- Notes: Keep expected session/task/run rules centralized here and in `pipeline_utils.py`.

### `check_shell_syntax.sh`
- Status: Repository validation.
- Purpose: Run shell syntax checks and optional ShellCheck lint.
- Inputs: Tracked shell scripts and qsub files.
- Outputs: Terminal pass/fail status.
- Typical command: run `code/check_shell_syntax.sh` with Bash.
- Checker: Included in `make test`.
- Notes: Does not require imaging data or containers.

### `validate_repo.py`
- Status: Repository validation.
- Purpose: Check JSON files, README paths, and repository hygiene.
- Inputs: Repository files.
- Outputs: Terminal pass/fail status.
- Typical command: run `code/validate_repo.py` with Python 3.
- Checker: Included in `make test`.
- Notes: Helps prevent generated outputs and stale path references from creeping back in.

### `pipeline_common.sh`
- Status: Shared shell configuration.
- Purpose: Define Linux2 paths, project-root detection, subject parsing, and job helpers.
- Inputs: Environment overrides and checkout location.
- Outputs: Shell functions and variables for wrappers.
- Typical command: sourced by shell scripts.
- Checker: `bash -n`, ShellCheck, and wrapper dry-runs.
- Notes: Project outputs stay checkout-relative.

### `pipeline_utils.py`
- Status: Shared Python helper.
- Purpose: Implement subject parsing, expected runs, IntendedFor logic, and completion helpers.
- Inputs: Paths and metadata from Python scripts/checkers.
- Outputs: Parsed structures and validation decisions.
- Typical command: imported by Python scripts and tests.
- Checker: `make test`.
- Notes: Prefer adding behavior here when it needs unit tests.

### `print_subjects.py`
- Status: Shared helper.
- Purpose: Normalize subject-list parsing for shell scripts.
- Inputs: Subject-list file.
- Outputs: One normalized subject ID per line.
- Typical command: called by `pipeline_common.sh`.
- Checker: Wrapper dry-runs and tests.
- Notes: Accepts `10001` and `sub-10001` forms.

### `convert_SocialDoorsBids.m`
- Status: Task helper.
- Purpose: Convert Social Doors/Doors behavioral events into BIDS event files.
- Inputs: Task event sources and `sublist-new.txt`.
- Outputs: BIDS event TSV files.
- Typical command: run in MATLAB when event conversion is needed.
- Checker: Manual event-file review.
- Notes: Handles both RF1-SRA sessions.

### `bet-flair.sh`
- Status: Optional anatomical QC helper.
- Purpose: Run FSL BET-style FLAIR processing.
- Inputs: FLAIR/T1 anatomical files.
- Outputs: Derived FLAIR masks or intermediate files.
- Typical command: run only for anatomical QC workflows.
- Checker: Visual/anatomical QC.
- Notes: Not part of the routine fMRI preprocessing path.

### `bet-flair-coverage.sh`
- Status: Optional anatomical QC helper.
- Purpose: Summarize FLAIR brain-extraction coverage.
- Inputs: FLAIR masks and anatomical references.
- Outputs: Coverage diagnostics.
- Typical command: run only for anatomical QC workflows.
- Checker: Visual/anatomical QC.
- Notes: Not part of the routine fMRI preprocessing path.

### `check-wm-mask.sh`
- Status: Optional anatomical QC helper.
- Purpose: Check white-matter mask coverage.
- Inputs: fMRIPrep/FreeSurfer anatomical outputs.
- Outputs: Mask diagnostics.
- Typical command: run only for anatomical QC workflows.
- Checker: Visual/anatomical QC.
- Notes: Not part of the routine fMRI preprocessing path.

### `create-T2.sh`
- Status: Optional anatomical QC helper.
- Purpose: Create or prepare T2-style anatomical derivatives.
- Inputs: Anatomical inputs expected by the script.
- Outputs: T2/anatomical helper outputs.
- Typical command: run only for anatomical QC workflows.
- Checker: Visual/anatomical QC.
- Notes: Not part of the routine fMRI preprocessing path.

### `extract_icv_fmriprep.py`
- Status: Optional anatomical QC helper.
- Purpose: Extract intracranial-volume style summaries from fMRIPrep derivatives.
- Inputs: fMRIPrep anatomical derivatives.
- Outputs: ICV summary tables.
- Typical command: run only for anatomical QC workflows.
- Checker: Review generated summaries.
- Notes: Not part of the routine fMRI preprocessing path.

### `flair-metrics.sh`
- Status: Optional anatomical QC helper.
- Purpose: Build FLAIR metric summaries.
- Inputs: FLAIR/anatomical derivatives.
- Outputs: Metric tables.
- Typical command: run only for anatomical QC workflows.
- Checker: Review generated summaries.
- Notes: Not part of the routine fMRI preprocessing path.

### `flair-outliers.sh`
- Status: Optional anatomical QC helper.
- Purpose: Identify FLAIR metric outliers.
- Inputs: FLAIR metric tables.
- Outputs: Outlier summaries.
- Typical command: run only for anatomical QC workflows.
- Checker: Review generated summaries.
- Notes: Not part of the routine fMRI preprocessing path.

### `flair-outliers.txt`
- Status: Optional anatomical QC artifact.
- Purpose: Store FLAIR outlier notes or IDs used by helper scripts.
- Inputs: Manual/QC review.
- Outputs: Text list.
- Typical command: not executable.
- Checker: Manual review.
- Notes: Keep separate from routine fMRI production decisions.

### `flair_to_mni_flirt.py`
- Status: Optional anatomical QC helper.
- Purpose: Register FLAIR-derived data to MNI with FLIRT-style transforms.
- Inputs: FLAIR images, references, and transform settings.
- Outputs: MNI-space FLAIR derivatives.
- Typical command: run only for anatomical QC workflows.
- Checker: Visual/anatomical QC.
- Notes: Not part of the routine fMRI preprocessing path.

### `voxel-count-L1.sh`
- Status: Optional anatomical QC helper.
- Purpose: Count voxels for L1/anatomical masks.
- Inputs: Mask files.
- Outputs: Voxel-count summaries.
- Typical command: run only for anatomical QC workflows.
- Checker: Review generated summaries.
- Notes: Not part of the routine fMRI preprocessing path.

### `README.md`
- Status: Documentation.
- Purpose: Explain this code directory and production workflow.
- Inputs: Maintainer edits.
- Outputs: Operator documentation.
- Typical command: read before running production stages.
- Checker: `make test` README-path checks.
- Notes: Keep aligned with the top-level README and `rf1-dwi`.

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
SUBLIST=sublist-new.txt
PREP_JOBS=6
MRIQC_JOBS=8
WARPKIT_JOBS=8
FMRIPREP_JOBS=2
TEDANA_JOBS=8

bash run_prepdata.sh --sublist "$SUBLIST" --jobs "$PREP_JOBS" --dry-run
bash run_mriqc.sh --sublist "$SUBLIST" --jobs "$MRIQC_JOBS" --dry-run
bash run_warpkit.sh --sublist "$SUBLIST" --jobs "$WARPKIT_JOBS" --dry-run
python3 addIntendedFor.py --sublist "$SUBLIST" --dry-run
bash run_fmriprep.sh --sublist "$SUBLIST" --jobs "$FMRIPREP_JOBS" --dry-run
bash run_tedana.sh --sublist "$SUBLIST" --jobs "$TEDANA_JOBS" --dry-run
python3 genTedanaConfounds.py --sublist "$SUBLIST" --dry-run
```

Remove `--dry-run` after reviewing the planned commands. Use `--sublist FILE`
only for an exceptional review, recovery run, or intentionally separate
validation list.

After each real stage, run the corresponding completion check:

```bash
bash check_bids.sh --sublist "$SUBLIST"
bash check_mriqc.sh --sublist "$SUBLIST"
bash check_warpkit.sh --sublist "$SUBLIST"
bash check_fmriprep.sh --sublist "$SUBLIST"
bash check_tedana.sh --sublist "$SUBLIST"
```

Each check exits nonzero when expected files are missing and prints a final
`CHECK PASSED` or `CHECK FAILED` summary suitable for the end of an ignored
stage log.

When changing Warpkit versions or switching between native/container backends,
do not mix fieldmaps in the same batch. Test one representative run with
`warpkit.sh --overwrite`, then rerun `run_warpkit.sh --overwrite`,
`addIntendedFor.py`, and the Warpkit/IntendedFor checks for the affected
subject list before resuming fMRIPrep.

To create a Git-trackable run record without committing bulky raw logs:

```bash
bash run_logged.sh --label fmriprep -- \
  bash run_fmriprep.sh --sublist "$SUBLIST" --jobs 3 \
  --check bash check_fmriprep.sh --sublist "$SUBLIST"
```

The raw output goes to ignored `logs/runs/`; the compact Markdown record goes
to tracked `logs/records/`. The `--` marker means `run_logged.sh` options stop
there and the real command starts after it. The optional `--check` marker starts
a checker command that runs only after the main command succeeds. Without a
checker the record says `Check exit: none`; if the main command fails, the check
is skipped and the record says `Check exit: skipped`. Use
`--include-full-log` only for small successful diagnostic commands whose full
terminal output belongs in the Markdown record.

For new users, the clearest pattern is often to log the run and the checker as
two separate commands:

```bash
bash run_logged.sh --label fmriprep-run -- \
  bash run_fmriprep.sh --sublist "$SUBLIST" --jobs 3

bash run_logged.sh --label fmriprep-check -- \
  bash check_fmriprep.sh --sublist "$SUBLIST"
```

## Linux2 Paths

The pipeline assumes the standard Smith Lab Linux2 source-data and tool layout.
Operators should not edit paths for routine runs. The project root is derived
from the checkout location. Production should run from
`/ZPOOL/data/projects/rf1-sra-linux2`; an intentional validation clone can
still write to its own `bids/`, `derivatives/`, and `logs/` directories while
reading the same source DICOMs and containers.

| Item | Path/configuration |
| --- | --- |
| Production checkout | `/ZPOOL/data/projects/rf1-sra-linux2` |
| Source DICOMs | `/ZPOOL/data/sourcedata/sourcedata/rf1-sra` |
| Scratch | `/ZPOOL/data/scratch` |
| Tool/container directory | `/ZPOOL/data/tools` |
| HeuDiConv | `/ZPOOL/data/tools/heudiconv-1.4.0.sif` |
| MRIQC | `/ZPOOL/data/tools/mriqc-24.0.2.simg` |
| fMRIPrep | `/ZPOOL/data/tools/fmriprep-25.2.5.simg` |
| Warpkit | Native `wk-medic` from `pip install warpkit`; legacy fallback `/ZPOOL/data/tools/warpkit.sif` |
| TemplateFlow | `/ZPOOL/data/tools/templateflow` |
| FreeSurfer license | `/ZPOOL/data/tools/licenses/fs_license.txt` |

## Choosing `--jobs`

Start with the defaults unless Linux2 is busy or a stage is being debugged:
predata uses 6 subject/session jobs, MRIQC uses 8 subject/session jobs,
Warpkit uses 8 subject/session/task/run jobs, fMRIPrep uses 2 subject jobs, and
TEDANA uses 8 subject jobs. Each wrapper prints its subject list and job plan
before launching.

Use `--jobs 1` when isolating a failure. Raise concurrency only when the dry-run
and first real subject look healthy, and avoid stacking multiple heavy stages at
high concurrency.

## fMRIPrep Resource Use

`run_fmriprep.sh --jobs N` controls participant-level concurrency. The wrapper
also divides the fixed Linux2 fMRIPrep budget across those jobs and exports the
per-subject values passed to fMRIPrep as `--nprocs`, `--omp-nthreads`, and
`--mem`. Current defaults reserve up to 96 fMRIPrep CPU threads and 196000 MB
RAM across all simultaneous fMRIPrep subjects, with 8 OpenMP threads per
process. For example, `--jobs 3` gives each subject `--nprocs 32`,
`--omp-nthreads 8`, and roughly 65 GB RAM.

## Overwrite Behavior

Use `--overwrite` only when replacing valid existing outputs is intentional.
`prepdata.sh` runs HeuDiConv in scratch first and checks that the staged BIDS
session exists. Only after that check passes does it remove the existing live
BIDS session and move the staged session into place. This keeps failed
conversion attempts from destroying the last valid copy while also keeping the
live `bids/` tree free of non-BIDS backup folders.

`warpkit.sh` deletes only explicit generated fieldmap outputs when
`--overwrite` is supplied.

## Session And Task Rules

The current session/task/run rules are centralized in `pipeline_utils.py` and
covered by tests. Preserve these rules unless David or Jacob confirms a
scientific correction:

| Session | Tasks | Runs |
| --- | --- | --- |
| `ses-01` | `ugr`, `trust`, `sharedreward`, `doors`, `socialdoors` | UGR/Trust/Shared Reward runs 1-2; Doors/Social Doors run 1 |
| `ses-02` | `ugr`, `doors`, `socialdoors` | UGR runs 1-2; Doors/Social Doors run 1 |

`run_prepdata.sh` and `run_mriqc.sh` try `ses-01` and `ses-02` for each subject;
optional missing `ses-02` source data are reported as skips. Warpkit and TEDANA
iterate the expected task/run set for each existing BIDS session and skip
task/runs that have no BIDS echo input. The checkers should therefore report
what they skipped and fail only when an expected output is missing for an
available input.

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

fMRIPrep completion checks look for the subject HTML report, expected per-run
preprocessed echo and confounds files, a completed FreeSurfer subject under
`derivatives/freesurfer`, and at least one fsLR CIFTI dtseries when the subject
has BOLD inputs. FreeSurfer/CIFTI generation makes fMRIPrep slower than the
previous volume-only run, but creates derivatives that a separate DWI workflow
can reuse later. TEDANA completion checks look for denoised BOLD, mixing matrix,
and metrics files for task/runs that have BIDS echo inputs.
`genTedanaConfounds.py --sublist FILE` then builds FSL-ready confound TSVs only
for TEDANA metric files matching that subject list. These checks and generated
tables are operational completion products, not scientific validation.

## Full-Cohort MRIQC And Outlier Review

Run cohort-level MRIQC and metric/outlier summaries only after the full
participant batch has completed participant-level MRIQC. This follows the R21
resting-state workflow pattern: participant MRIQC first, the MRIQC group report
afterward, then run/subject metric summaries and outlier review. Do not treat
`extract-metrics.py` output as a routine new-subject validation requirement.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash mriqc_group.sh --dry-run
bash mriqc_group.sh
python3 extract-metrics.py --sublist sublist-new.txt --dry-run
python3 extract-metrics.py --sublist sublist-new.txt
```

`extract-metrics.py` collects run-level `tsnr` and `fd_mean` from MRIQC JSON
files; replace `sublist-new.txt` with the final cohort subject list if that
list lives somewhere else. Any run or subject outlier decisions should be made
and documented with the group MRIQC review, not as automatic per-batch
exclusions.

## Failure Reports

When something fails, send David or Jacob:

1. The exact command.
2. The newest Markdown file in `logs/records/`.
3. Whether `Command exit` and `Check exit` are 0.
4. The first `CHECK FAILED`, `ERROR`, or missing-file line.
5. The expected subject/session/task/run coverage, especially whether `ses-02`
   or a missing task/run was supposed to be present.

## Tests

From the repository root:

```bash
make test
```

The tests cover subject-list parsing, session/task/run selection, scanner
heuristic selection around the preserved March 4 cutoff, IntendedFor generation
for present/missing runs, atomic metadata writes, unsafe path refusal, Warpkit
input manifests, and fMRIPrep/TEDANA completion checks.

## Linux2 Validation Checklist

Use this checklist for any future workflow change or separate validation clone:

1. Record the commit SHA, checkout path, and container versions.
2. Keep the production `main` checkout protected unless the operator has
   intentionally chosen to run from it.
3. Select a minimal representative set: one pre-upgrade `ses-01` case, one
   post-upgrade `ses-01` case, one `ses-02` subject, and one intentionally
   absent task/run when available. Prefer overlap with the `rf1-dwi` validation
   subjects, such as `10317` and `10953`, when they cover these needs.
4. Store the validation list under `logs/validation/` or another review-only
   location rather than replacing `sublist-new.txt`.
5. Run every stage first with `--dry-run` or validation mode.
6. Compare outputs with trusted production outputs when available.
7. Record every command, exit code, and unexpected warning.
8. Confirm raw DICOM source data were not changed.
9. Confirm no existing production BIDS or derivatives were removed except where
   `--overwrite` was intentionally used.
10. Run the BIDS validator after conversion and fieldmap metadata changes.
11. Verify expected subject/session/task/run coverage.
12. Confirm all `IntendedFor` paths resolve to existing BOLD files.
13. Confirm fieldmap units and metadata.
14. Confirm fMRIPrep reports, expected session-level outputs, fsLR CIFTI
   outputs, and `derivatives/freesurfer/sub-*/scripts/recon-all.done`.
15. Confirm TEDANA denoised outputs, mixing matrices, and metrics files.
16. Confirm confound row counts match the corresponding BOLD time series.
17. Confirm MRIQC participant outputs exist for the validation subjects.
18. Defer `mriqc_group.sh`, `extract-metrics.py`, and run/subject outlier
   review until the full participant batch is complete.
19. Run `make test`.
20. Document the commit SHA tested, subjects/sessions tested, stages tested,
   pass/fail result, and discrepancies.

## Still To Confirm

The scanner-upgrade cutoff needs Linux2 confirmation. The code has used
March 4, 2025; comments historically said March 18, 2025. This branch preserves
the March 4 behavior until Jacob confirms otherwise.
