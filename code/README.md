# Code Manual

All repository scripts live in this directory. Routine batch processing should
not require editing scripts: update `sublist-new.txt`, then run the standard
stage commands below.

## Upstream/Downstream Boundary

`rf1-sra-linux2` runs before `rf1-dwi`. This repository owns the shared RF1-SRA
BIDS dataset, including canonical behavioral `_events.tsv` files, plus
fMRIPrep, FreeSurfer, CIFTI, TEDANA, MRIQC, confound derivatives, and
cohort-level metric summaries. Downstream analysis repositories consume these
BIDS events and should not read private raw behavioral logs directly. The DWI
repository should consume validated upstream outputs for QSIPrep/QSIRecon
instead of copying or regenerating them.

The dependency map is:

```text
Raw DICOMs / XNAT
  + private behavioral logs
  -> rf1-sra-linux2 imaging and behavioral BIDS conversion
  -> rf1-sra-linux2 Warpkit / IntendedFor
  -> rf1-sra-linux2 fMRIPrep / FreeSurfer / CIFTI
  -> rf1-sra-linux2 post-fMRIPrep geometry audit / reviewed repair
  -> rf1-sra-linux2 TEDANA / MRIQC / confounds
  -> rf1-sra-linux2 cohort-level run imaging QC
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
| 2 | `run_prepdata.sh` | `prepdata.sh`, imaging heuristics, `convert_behavior.py`, `shiftdates.py` | `sublist-new.txt`, DICOMs, private task logs | Complete BIDS session with imaging and canonical events | Stages conversion, defacing, date shifting, and events validation in scratch. Check with `check_bids.sh`. |
| 3 | `run_warpkit.sh` | `warpkit.sh`, `record_warpkit_reuse.py` | BIDS multi-echo mag/phase files and JSON; reviewed `warpkit_reuse.tsv` exceptions | BIDS `fmap/` fieldmap and magnitude files | Removes only explicit generated fmap files when `--overwrite` is used. Normal estimates finish before reviewed reuse jobs. Check with `check_warpkit.sh`. |
| 4 | `addIntendedFor.py` | `pipeline_utils.py` | BIDS `fmap/*.json`, existing BOLD files | Updated fieldmap JSON | Atomic writes; `--dry-run` available. |
| 5 | `run_fmriprep.sh` | `fmriprep.sh`, `fmriprep_config.json` | BIDS data | `derivatives/fmriprep`, `derivatives/freesurfer` | Generates volumetric, fsLR CIFTI, and FreeSurfer outputs; skips only when practical completion outputs exist. |
| 6 | `fmriprep_geometry.py` | nibabel, ANTs in the pinned fMRIPrep container | Every non-echo volumetric MNI fMRIPrep BOLD | Audit reports; reviewed in-place canonical repairs plus preserved originals/provenance | Audit is read-only. Repair requires `--apply`, never targets BIDS, and atomically replaces only audited fMRIPrep outliers. |
| 7 | `run_tedana.sh` | `tedana.sh` | fMRIPrep echo outputs, BIDS echo metadata | `derivatives/tedana` | Logs missing optional runs under `logs/`. |
| 8 | `genTedanaConfounds.py` | pandas | fMRIPrep confounds, TEDANA mixing/metrics | `derivatives/fsl/confounds_tedana` | Atomic TSV writes; row-count validation. |
| 9 | `run_mriqc.sh` | `mriqc.sh` | BIDS data | `derivatives/mriqc` | Container run only; no raw-source edits. |
| 10 | `mriqc_group.sh` | MRIQC container | Completed participant MRIQC outputs | MRIQC group report | Cohort-level step; run after the full participant batch completes. |
| 11 | `build_run_qc.py` | BIDS, MRIQC, fMRIPrep, TEDANA, and `qc/qc_policy.json` | Tracked canonical TSV/JSON, four workbooks, four histograms, and fixed coverage target under `qc/` | Cohort-level builder/checker; source exclusions are omitted by default, missing metrics remain incomplete, and canonical replacement requires `--overwrite`. |

`audit_tedana.py`, `benchmark_tedana.py`, `audit_tedana_design.py`, and the
TEDANA summarizers are an audit-only scientific
validation branch from completed production TEDANA, not additional production
pipeline stages. They read production inputs but write only under
`qc/tedana_audit/` and ignored `derivatives/tedana-audit/`.

`make_repair_runlists.py` is the filesystem audit helper for recovery runs. It
does not launch processing; it writes targeted runlists and a missing-path TSV
under `logs/runlists/`.

## Behavioral Provenance

Production conversion has no runtime dependency on another Git repository.
Private logs stay under `/ZPOOL/data/projects/rf1-sra/stimuli`, and only
canonical BIDS events and aggregate, non-identifying audit counts belong in the
Linux2 workflow. Historical repositories are reference material only:

- `r01-soi` contains the corrected legacy Shared Reward outcome conversion.
- `sharedreward-aging` contains a stale converter that started outcomes at the decision onset.
- `rf1-sra-trust`, `rf1-betrayal`, and `r01-soi` contain legacy Trust implementations.
- `rf1-sra-ugr` contains the legacy GLM-oriented UGR conversion.
- `rf1-norms` and `rf1-betrayal` contain historical UGR model generation that reads private CSVs and will be migrated separately.
- `rf1-wave2` is historical/side-project code and is not authoritative.
- `rf1-sra-linux2` is the authoritative production implementation going forward.

The converter follows executed task code and measured timestamps before legacy
analysis conventions. An aggregate local audit found Trust outcomes centered
at about 2.00 seconds rather than the legacy hard-coded 1 second. Across more
than 30,000 usable historical UGR trials, stored `cue_Onset` was about 0.5
seconds later than the true partner-cue onset, while `decision_onset - ISI`
matched the logged endowment boundary within milliseconds. The production UGR
derivation therefore reconstructs the partner-only cue from
`decision_onset - ISI - 1.5` and documents that timing in the task sidecar.

The development parity audit classifies the intentional differences this way:

| Task | Classification | Canonical difference |
| --- | --- | --- |
| Shared Reward | Expected correction | Outcome rows retain the historical partner/outcome labels but use measured outcome boundaries; a miss becomes separate `missed_decision` and `missed_outcome` rows. |
| Shared Reward | Expected schema change | Partner, feedback, and stable trial identifiers are explicit columns. |
| Trust | Expected correction | Positive-investment outcomes use `outcome_offset - outcome_onset`; zero investments do not acquire invented outcomes. |
| UGR | Expected correction | The true partner-cue onset and visible endowment interval are reconstructed from the executed task sequence. |
| UGR | Expected schema change | Phase rows and trial attributes replace duplicated GLM labels such as condition and condition-plus-choice rows. |
| Social Doors/Doors | Expected schema continuity | Existing decision, feedback, response, and stimulus columns are retained while source ambiguity becomes an error. |

Partner identity, outcome category, trust value, reciprocation, sociality,
endowment, offer, left/right response, and accept/reject choice are never
treated as expected differences. A disagreement in those values requires
investigation before backfill.

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
- Outputs: `logs/runlists/*_*-repair.txt`, `*_source-excluded.txt`, `*_source-missing.txt`, `*_fmriprep-ready.txt`, `*_fmriprep-incomplete.txt`, and `*_missing-paths.tsv`.
- Typical command: `python3 make_repair_runlists.py --sublist "$SUBLIST" --prefix repair-$(date +%Y%m%d)`.
- Checker: Review the missing-path TSV and rerun the relevant stage checkers after repair runs.
- Notes: Subjects with source folders under `/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions` are written to `source-excluded` and omitted from repair/ready counts. `source-missing` subjects need source DICOM download/triage before `prepdata.sh` can repair them. `sub-11891` has a documented nested source layout under `/ZPOOL/data/sourcedata/sourcedata/rf1-sra/11891/Smith-SRA-11891/Smith-SRA-11891/scans`; `sub-12018` retains the malformed downloaded inner path `/ZPOOL/data/sourcedata/sourcedata/rf1-sra/Smith-SRA-12018/Smith-SRA-/scans`. `fmriprep-ready` excludes subjects with BIDS/WarpKit/IntendedFor prerequisite issues; MRIQC is tracked separately because it is QC, not an fMRIPrep prerequisite.

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
- Purpose: Launch imaging and behavioral BIDS conversion for every listed subject and session.
- Inputs: `sublist-new.txt`, raw DICOMs, private task logs, and `prepdata.sh`.
- Outputs: BIDS sessions, canonical events, defaced T1w images, and shifted `scans.tsv` files.
- Typical command: `bash run_prepdata.sh --sublist "$SUBLIST" --jobs 6`.
- Checker: `bash check_bids.sh --sublist "$SUBLIST"`.
- Notes: Prints the subject list and job plan before launching.

### `prepdata.sh`
- Status: Production worker.
- Purpose: Run one subject/session through staged imaging and behavioral BIDS conversion, defacing, date shifting, and validation.
- Inputs: One subject/session, DICOMs, task logs, HeuDiConv, heuristics, `supplemental_sources.tsv`, `convert_behavior.py`, and `shiftdates.py`.
- Outputs: One staged and then live BIDS subject/session tree.
- Typical command: normally called by `run_prepdata.sh`.
- Checker: `check_bids.sh`.
- Notes: Stages all transformations and events validation before replacing live BIDS outputs; `--overwrite` is required for replacement. Matching existing events are preserved in the stage so missing private logs cannot silently erase curated behavior. Uses `PYDEFACE_CMD`, defaulting to `/ZPOOL/data/tools/anaconda/tug87422/envs/pydeface-2.1/bin/pydeface`; override that variable for another executable. Every generated T1w is defaced, including run-numbered T1w acquisitions. `sub-11891` session 01 uses its nested source-data path explicitly. Reviewed same-session return visits are combined only through `supplemental_sources.tsv` and a temporary scratch symlink view; sourcedata are not modified. Raw localizer and PhoenixZIPReport series remain in sourcedata, but HeuDiConv filters them during indexing.

### `source_layout.py`
- Status: Production helper.
- Purpose: Validate reviewed supplemental DICOM folders and stage a temporary combined scan view for one BIDS session.
- Inputs: Subject/session, source root, and `supplemental_sources.tsv`.
- Outputs: A scratch-only symlink inventory and HeuDiConv DICOM template.
- Typical command: normally called by `prepdata.sh`; inspect a declaration with `python3 source_layout.py count --manifest supplemental_sources.tsv --subject 11116 --session 02`.
- Checker: `tests/test_source_layout.py`, the `prepdata.sh --dry-run` plan, and `check_bids.sh` after conversion.
- Notes: Manifest paths must be relative, every declared folder must contain DICOMs, and nothing under sourcedata is changed.

### `supplemental_sources.tsv`
- Status: Reviewed production exception registry.
- Purpose: Declare additional source folders that belong to an existing scientific/BIDS session.
- Inputs: Subject, session, `active`/`paused` status, source-relative folder, and a human-readable reason.
- Outputs: A fail-closed input to `source_layout.py` and `prepdata.sh`.
- Typical command: do not run directly; add a row only after acquisition identity and session assignment are reviewed.
- Checker: `python3 source_layout.py count ...` and `prepdata.sh --dry-run`.
- Notes: It does not authorize source modification or a new BIDS session. A `paused` row blocks conversion for the entire session. Full post-fix behavior for `sub-11116` was recovered in private-repository commit `7c6f768d0`; DICOM timestamps match the later completed Doors execution and the completed Faces execution with a stable approximately 252.8-second clock offset. Its reviewed `active` row enables the same-session DICOM merge.

### `convert_behavior.py`
- Status: Canonical production converter.
- Purpose: Convert Shared Reward, Trust, UGR, Social Doors, and Doors task logs into BOLD-matched BIDS events.
- Inputs: One subject/session, private behavior root, staged or live BIDS root, selected tasks, and `behavior_curation.tsv`.
- Outputs: Session `_events.tsv` files and inheritance-compatible task-level events JSON sidecars.
- Typical command: `python3 convert_behavior.py --subject 10001 --session 01 --overwrite`; add `--tasks sharedreward --run 1` for an exact reviewed run.
- Checker: `python3 check_events.py --subject 10001 --session 01`.
- Notes: Trust/UGR raw `run-0/run-1` translation, Shared Reward one-based `run-1/run-2`, and explicit/implicit session resolution are deliberate; ambiguous mappings fail. `--run` limits conversion to an exact BIDS run after review. Field-count mismatches, repeated headers, trial resets, onset resets, and internal malformed executed rows are hard failures. Explicit `ran=0` placeholders are omitted. A final interrupted trial may be omitted only when all later rows are explicit placeholders; the omission is reported and the resulting short run still needs exact fingerprint-bound approval. Shared Reward misses retain decision and feedback rows, Trust uses measured feedback offsets, and historical UGR cue timing is reconstructed from `decision_onset` and ISI after aggregate validation of the private logs. Atomic events writes preserve the permissions ordinary file creation would receive under the inherited umask instead of retaining `mkstemp()`'s private `0600` mode.

### `behavior_curation.tsv`
- Status: Reviewed production exception registry.
- Purpose: Record independent approval of coherent short runs or behaviorally poor runs.
- Inputs: One row per approved issue with subject/session/task/run, source SHA-256, trial fingerprint, reviewer, and rationale.
- Outputs: Fingerprint-bound approvals consumed by the converter and checker.
- Typical command: edit only after reviewing a row from `check_events.py --review-tsv ...`.
- Checker: `python3 check_events.py --sublist "$SUBLIST"` validates the schema and fingerprints.
- Notes: `unexpected_trial_count` and `behaviorally_poor` approve coherent exceptions without clearing their downstream run-QC flags. `ambiguous_run_label` remains available for exceptional fingerprint-bound mappings, but ordinary Shared Reward `run-1` is one-based and needs no ambiguity approval. Do not approve appended runs, malformed tables, or competing source files; repair the private source instead. Do not commit trial-level data.

### `run_convert_behavior.sh`
- Status: Production backfill wrapper.
- Purpose: Generate canonical events for existing BIDS sessions without rerunning HeuDiConv.
- Inputs: Subject list, selected sessions/tasks, private behavior root, and BIDS BOLD runs.
- Outputs: Canonical BIDS events and task-level sidecars.
- Typical command: preview existing BIDS data with `bash run_convert_behavior.sh --sublist "$SUBLIST" --jobs 4 --dry-run --overwrite`, then remove `--dry-run` after review.
- Checker: `python3 check_events.py --sublist "$SUBLIST"`.
- Notes: This is a modular backfill stage, not a run-all wrapper. Use `--dry-run` before a cohort overwrite. The shared subject reader makes the production source-exclusions root authoritative across shell stage wrappers and shell checkers, even if residual BIDS or production-source copies exist. `--include-source-excluded` is an explicit forensic override; other shell scripts may use `RF1_INCLUDE_SOURCE_EXCLUDED=1` for the same narrow purpose. Pass an explicitly filtered list to Python-only audits such as `check_events.py`.

### `check_events.py`
- Status: Behavioral BIDS checker.
- Purpose: Audit private source, BOLD, events, ambiguity, conversion validity, trial counts, and curation status as distinct states.
- Inputs: Subject or subject list, sessions/tasks, private behavior root, and BIDS root.
- Outputs: Per-run statuses, aggregate counts, optional machine-readable review TSV, and a final pass/fail result.
- Typical command: `python3 check_events.py --sublist "$SUBLIST" --review-tsv ../logs/reviews/events-audit.tsv`; use `--subject 10617 --session 01 --tasks sharedreward --run 1` for an exact-run repair check.
- Checker: Ends with `CHECK PASSED` or `CHECK FAILED`.
- Notes: Source/BOLD absences are reported separately. When an events file is absent but its source exists, the checker parses that source first so malformed data and fingerprint-bound review issues are reported as their actual blockers instead of generic missing output. Source absence, missing/malformed events, canonical-content disagreement, and unapproved review issues fail. Review reports contain identifiers, paths, hashes, and reasons but no trial-level values.

### `audit_openneuro_events.py`
- Status: Optional historical run-identity audit.
- Purpose: Compare ordered private-source trial identity with a local snapshot of OpenNeuro `ds005123` version `1.1.3` and detect likely run swaps; onset and duration are intentionally excluded.
- Inputs: Subject list, production BIDS run inventory, private behavior root, and local OpenNeuro snapshot.
- Outputs: TSV statuses for same-run match, other-run match, partial/duplicated historical match, ambiguous-label evidence, mismatch, unavailable reference, and conversion failure.
- Typical command: `python3 audit_openneuro_events.py --sublist "$SUBLIST" --openneuro-root /path/to/ds005123-1.1.3 --report-tsv ../logs/reviews/openneuro-events.tsv`.
- Checker: Nonzero exit for mismatches and swap risks unless `--informational` is used.
- Notes: OpenNeuro is a frozen historical witness, not production input or a full events validator. Doors/Social Doors provide the closest comparison. Trust allows ordered partial matches when the public export omitted trials; Shared Reward treats private misses as outcome wildcards; UGR compares only sociality/endowment order. Known public-data issues require human interpretation of mismatches.

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
- Notes: The March 4, 2025 cutoff remains the current production behavior. A single T1w keeps the historical unsuffixed name; multiple T1w acquisitions are emitted as `run-1`, `run-2`, and so on. Uses the same localizer/PhoenixZIPReport filename filter as `heuristics_rf1.py`.

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
- Notes: Uses the shared native `wk-medic` executable at `/ZPOOL/data/tools/anaconda/tug87422/envs/warpkit-1.4.0/bin/wk-medic` by default. This path is shared lab tooling despite the username in the path. Override `WARPKIT_CMD` only for a tested alternate executable. Set `WARPKIT_BACKEND=apptainer` only to use the legacy container fallback. Set `WARPKIT_N_CPUS`, `OMP_THREADS`, `JULIA_NUM_THREADS`, or `JULIA_NUM_GC_THREADS` to tune per-run concurrency. Runs ordinary WarpKit estimates first and reviewed `warpkit_reuse.tsv` entries second so source fieldmaps exist before reuse.

### `warpkit.sh`
- Status: Production worker.
- Purpose: Generate fieldmap and magnitude products for one subject/session/task/run.
- Inputs: Four magnitude images, phase images, phase JSON files, Warpkit, and FSL.
- Outputs: BIDS `fmap/*` NIfTI/JSON files and `derivatives/warpkit` markers.
- Typical command: normally called by `run_warpkit.sh`.
- Checker: `check_warpkit.sh`.
- Notes: `--overwrite` deletes only explicit generated fieldmap and Warpkit derivative products. The worker supports default `WARPKIT_BACKEND=native` and fallback `WARPKIT_BACKEND=apptainer`, passes `WARPKIT_N_CPUS` through to WarpKit, and logs the backend/thread plan. A reviewed reuse copies only the source fieldmap, creates the target run's magnitude reference from its own echo-1 BOLD, and writes reuse metadata and provenance before marking completion.

### `warpkit_reuse.tsv`
- Status: Reviewed production exception manifest.
- Purpose: Declare exact target runs allowed to reuse an already generated same-task WarpKit fieldmap.
- Inputs: Subject, session, task, target run, source run, and neutral reason code.
- Outputs: Decisions consumed by WarpKit wrappers, workers, checkers, and repair audits.
- Typical command: do not execute; edit only after scientific review.
- Checker: `bash check_warpkit.sh --sublist "$SUBLIST"` and `make_repair_runlists.py`.
- Notes: The sole current entry is `sub-10929 ses-01 task-ugr run-2`, which reuses run 1 because its phase acquisition is incomplete. Adding a row is a scientific decision, not a convenience for ordinary missing files.

### `record_warpkit_reuse.py`
- Status: Production provenance helper.
- Purpose: Verify that a copied fieldmap exactly matches its reviewed source and record reuse metadata.
- Inputs: Source/target fieldmap paths, source JSON, exact run identifiers, and reason code.
- Outputs: Target fieldmap JSON metadata plus `derivatives/warpkit/*_fieldmap-reuse.json` provenance.
- Typical command: normally called by `warpkit.sh` for a manifest-approved reuse.
- Checker: `check_warpkit.sh` requires the provenance JSON for reviewed reuse runs.
- Notes: Removes stale source `IntendedFor`; `addIntendedFor.py` then assigns only the target run's existing magnitude BOLD echoes.

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

### `build_run_qc.py`
- Status: Canonical cohort-level production QC builder and checker.
- Purpose: Inventory acquired functional runs, collect four run imaging metrics, calculate one-pass one-sided Tukey fences, and generate reproducible review artifacts.
- Inputs: BIDS echo-2 part-mag BOLD inventory; MRIQC echo-2 part-mag JSON; TEDANA `desc-tedana_metrics.tsv`; non-echo fMRIPrep `MNI152NLin6Asym` run brain masks; `qc/qc_policy.json`; TemplateFlow resolution-02 brain mask; and the checksum-pinned historical cerebellum/brainstem exclusion mask.
- Outputs: `qc/run_qc.tsv`, `qc/thresholds.tsv`, `qc/socialdoors_pair_qc.tsv`, `qc/provenance.json`, a fixed target mask, four XLSX workbooks, and four histogram PNGs.
- Typical command: `"$QC_PYTHON" build_run_qc.py build --dry-run`, then run the production build and checker through `run_logged.sh --include-full-log` after review.
- Checker: `"$QC_PYTHON" build_run_qc.py check`.
- Notes: `qc/run_qc.tsv` is authoritative; spreadsheets are generated views. Shared Reward, Trust, and UGR each use one paradigm distribution. Social Doors pools `task-socialdoors` and `task-doors` for thresholds while retaining separate run rows and a paired summary. Missing or ambiguous metrics produce `qc_status=incomplete`; no metric is silently zeroed. Existing canonical outputs require `build --overwrite`. Source-excluded subjects are omitted unless the forensic `--include-source-excluded` override is explicit. The retired MRIQC-only CSV extractor and legacy FEAT voxel counter must not be restored as competing production QC paths.

### `build_events_qc.py`

- Status: Canonical cohort-level behavioral response-QC builder and checker.
- Purpose: Quantify response misses in every supported BIDS events run, distinguish distributed misses from sustained terminal miss blocks, and identify runs that may merit reviewed terminal trimming.
- Inputs: Canonical BIDS `_events.tsv` files, `qc/events/policy.json`, an optional production subject list, and the authoritative source-exclusions directory.
- Outputs: `qc/events/results/run_response_qc.tsv`, `review_candidates.tsv`, `qc/events/results/provenance.json`, and two PNG summaries.
- Typical command: `"$QC_PYTHON" build_events_qc.py build --dry-run`, followed by `build --overwrite` after review.
- Checker: `"$QC_PYTHON" build_events_qc.py check`.
- Notes: With no `--sublist`, the current BIDS cohort is discovered automatically and authoritative source exclusions are omitted; use a subject list only for a deliberately frozen cohort snapshot. The historical 25% Social Doors/Doors rule is reported across tasks as a review threshold, not an automatic cross-task exclusion. Terminal-failure and salvage flags require human review. This script never edits BIDS or imaging data, and its onset fields are not approved trimming boundaries. The atomically replaced results directory preserves the permissions ordinary directory creation would receive under the inherited umask instead of retaining `mkdtemp()`'s private `0700` mode.

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
- Notes: Generates the upstream anatomy derivatives consumed by `rf1-dwi`. Each
  real invocation also writes an ignored subject-specific raw log under
  `logs/runs/*_fmriprep-sub-<ID>.log` for failures in concurrent batches.

### `fmriprep_config.json`
- Status: fMRIPrep configuration.
- Purpose: Filter multi-session fMRIPrep inputs for this dataset.
- Inputs: BIDS dataset metadata.
- Outputs: fMRIPrep BIDS filter settings.
- Typical command: not run directly.
- Checker: `check_fmriprep.sh` plus fMRIPrep reports.
- Notes: Keeps functional inputs to magnitude images.

### `fmriprep_geometry.py`
- Status: Production post-fMRIPrep audit and reviewed repair gate.
- Purpose: Audit every non-echo volumetric `MNI152NLin6Asym` preprocessed BOLD, derive the unique modal grid, preserve audited outliers, and repair canonical fMRIPrep geometry without downstream path exceptions.
- Inputs: `derivatives/fmriprep`, a frozen audit JSON for repair/verification, nibabel/numpy from the shared TEDANA environment, Apptainer, and the pinned fMRIPrep image.
- Outputs: `logs/geometry/*.json` and `*.tsv`; original NIfTI backups under `derivatives/fmriprep_geometry/originals/`; per-file and run-level provenance under `derivatives/fmriprep_geometry/repairs/`; corrected NIfTIs at their existing canonical fMRIPrep paths.
- Typical command: `"$GEOMETRY_PYTHON" fmriprep_geometry.py audit --report-prefix ../logs/geometry/fmriprep-geometry-$(date +%Y%m%d-%H%M%S)`; for metadata-only findings from that fresh audit, preview and apply `normalize-xforms --audit-json "$AUDIT_JSON" [--apply]`.
- Checker: `"$GEOMETRY_PYTHON" fmriprep_geometry.py verify --audit-json "$AUDIT_JSON"`.
- Notes: Audit has no subject filter and is read-only. It excludes `_echo-*` files and CIFTI outputs, reports every task/run, clusters spatial shape/effective affine with tolerance, and separately audits modal qform/sform matrices and intent codes. It fails closed on malformed images or a tied mode. Repair previews unless `--apply` is supplied, verifies that the complete inventory has not changed since audit, performs 4D identity resampling with ANTs/Lanczos interpolation, copies the modal transform metadata, validates every output volume, and atomically replaces only canonical fMRIPrep derivatives. Legacy repaired outputs with the correct lattice but ANTs' generic `1/1` codes receive a metadata-only repair and are not interpolated again. It never writes under `bids/`. The generated Insight-text identity transform must retain its `.txt` suffix so ITK does not select its MATLAB transform reader. Review every reported `sub-12013` task/run before applying the first production repair.

### `fmriprep_mask_geometry.py`
- Status: Production companion-derivative geometry gate.
- Purpose: Audit every canonical non-echo MNI BOLD against its corresponding fMRIPrep `desc-brain_mask`, then repair only reviewed mismatches without downstream path exceptions.
- Inputs: `derivatives/fmriprep`, a frozen companion-mask audit JSON, and nibabel/numpy/scipy from the shared imaging environment.
- Outputs: `logs/geometry/fmriprep-mask-*.json` and `.tsv`; preserved originals under `derivatives/fmriprep_geometry/mask_originals/`; provenance under `derivatives/fmriprep_geometry/mask_repairs/`; corrected masks at their canonical fMRIPrep paths.
- Typical command: `"$GEOMETRY_PYTHON" fmriprep_mask_geometry.py audit --report-prefix ../logs/geometry/fmriprep-mask-$(date +%Y%m%d-%H%M%S)`; preview `repair --audit-json "$MASK_AUDIT_JSON"`, then add `--apply` only after reviewing every mismatch.
- Checker: `"$GEOMETRY_PYTHON" fmriprep_mask_geometry.py verify --audit-json "$MASK_AUDIT_JSON"`.
- Notes: Uses nearest-neighbor resampling and binary output for spatial-grid mismatches; metadata-only mismatches copy qform/sform information without interpolation or voxel changes. It preserves the original with a checksum, atomically replaces only the mask, rejects inventory/checksum drift, and never writes under `bids/`.

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
- Notes: Prints the subject list, job plan, and pinned executable before launching. The default shared executable is `/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/tedana`; override `TEDANA_CMD` only for a tested alternate installation.

### `tedana.sh`
- Status: Production worker.
- Purpose: Run TEDANA for available task/runs for one subject.
- Inputs: fMRIPrep echo outputs and BIDS echo metadata.
- Outputs: Denoised BOLD, mixing matrix, component metrics, and per-run raw logs under `logs/runs/tedana/`.
- Typical command: normally called by `run_tedana.sh`.
- Checker: `check_tedana.sh`.
- Notes: Missing optional runs are logged and skipped when no BIDS echo input exists. The worker preflights `TEDANA_CMD` before entering the run loop, so a detached job cannot fail every run merely because its shell `PATH` differs from an interactive session. Failed per-run logs are tailed into the parent run record for remote diagnosis.

### `audit_tedana.py`
- Status: Read-only cohort scientific audit; not a production replacement.
- Purpose: Inventory every acquired multi-echo task run, validate fMRIPrep NSS regressors, summarize historical TEDANA dimensionality/classification/variance, fit Motion24 to component timecourses, and choose a reproducible sentinel set.
- Inputs: BIDS echo-2 run inventory and echo metadata, fMRIPrep echo images/confounds/native masks, historical `derivatives/tedana`, and the authoritative source-exclusion directory.
- Outputs: Tracked aggregate TSV/JSON/report/figures under `qc/tedana_audit`; ignored component rows under `derivatives/tedana-audit/current`.
- Typical command: `"$AUDIT_PYTHON" audit_tedana.py build --overwrite`; preview with `build --dry-run`.
- Checker: `"$AUDIT_PYTHON" audit_tedana.py check` verifies recorded checksums, row counts, and sentinel counts.
- Notes: Requires TEDANA 26.0.3 and records fMRIPrep 25.2.5. NSS regressors must be binary, one-hot, unique, and contiguous from volume zero. Motion24 fits drop exactly those validated rows and never alter classification. Task regressors are prohibited. The builder may report incomplete rows but still exits zero when it successfully records them.

### `benchmark_tedana.py`
- Status: Isolated sentinel experiment; not production processing.
- Purpose: Run controlled T2S-FULL versus T2S-EXCLUDE-NSS, matched FULL-FastICA versus NSS-FastICA, NSS-aware FastICA versus RobustICA, optional targeted KIC/MDL comparisons, and five prespecified FastICA seed conditions; reconstruct full-length audit images; and optionally calculate TEDANA-native Motion24 metrics without changing classifications.
- Inputs: `qc/tedana_audit/sentinel_runs.tsv`, pinned TEDANA/t2smap 26.0.3 executables, fMRIPrep echo images/native masks/confounds, and the completed audit-only `t2s-full` optcom used as the full-grid reference.
- Outputs: Ignored per-configuration derivatives, logs, status, external regressors, and provenance under `derivatives/tedana-audit`.
- Typical command: `"$AUDIT_PYTHON" benchmark_tedana.py plan --robustica-threads 4`; then follow the staged pilot commands in `qc/tedana_audit/README.md`.
- Checker: `"$AUDIT_PYTHON" benchmark_tedana.py check --configs ...` verifies expected outputs, raw and restored volume counts, and motion-tree classification identity.
- Notes: Every command explicitly sets curvefit and mask. T2* and FastICA jobs use one thread; `--robustica-threads` is passed to RobustICA as `n_jobs` for its 30 repeated ICA fits. Decomposition commands also set the requested PCA criterion, seed, ICA method, and `tedana_orig`. Ordinary configs use seed 42; seed sensitivity is restricted to 1, 10, 42, 100, and 1000. `full-fastica` explicitly uses zero dummy scans; `nss-fastica` differs only by the validated run-specific count. KIC/MDL are optional targeted configurations, never defaults. Requested configurations are queued together per sentinel so RobustICA does not wait behind every faster configuration. NSS-aware runs receive a numerically validated full-grid image and a zero-padded full-grid ICA matrix. Existing complete jobs skip, incomplete directories fail closed, and all removal/output paths are confined to `derivatives/tedana-audit`. Begin with the documented four-run pilot; never launch a full-cohort RobustICA rerun from this tool.

### `audit_tedana_design.py`
- Status: Read-only full-cohort scientific audit; not production processing.
- Purpose: Extract saved AIC/KIC/MDL PCA estimates and accepted/rejected overlap, reconstruct the exact TEDANA-plus-fMRIPrep nuisance matrix, compare existing generated confounds, and report classification burden, independent TEDANA rank cost, combined rank, descriptive tails, and pre-task residual degrees of freedom.
- Inputs: `qc/tedana_audit/current_runs.tsv`, production fMRIPrep confounds, TEDANA PCA/ICA metrics and mixing matrices, saved MAPCA cross-component JSON, and existing `derivatives/fsl/confounds_tedana` files when present.
- Outputs: Tracked cohort/review/scanner tables, a targeted PCA-method manifest, figure, report, and provenance under `qc/tedana_audit/design`.
- Typical command: `"$AUDIT_PYTHON" audit_tedana_design.py build --overwrite`; preview with `build --dry-run`.
- Checker: `"$AUDIT_PYTHON" audit_tedana_design.py check` validates cohort coverage, output checksums, current-run checksum, and the live input inventory.
- Notes: Task regressors are not used, so residual degrees of freedom are explicitly pre-task estimates. Percentile tails are descriptive review sets, not exclusions. Raw rejected count is subordinate to incremental nuisance rank, rejected fraction, and rejected variance. Accepted/rejected overlap is descriptive ICA QC, not evidence that RF1 removes accepted signal before fitting task EVs.

### `audit_tedana_nuisance_qc.py`
- Status: Audit-only; does not create production residualized BOLD.
- Purpose: Compare BASE, TEDANA-FULL, and TEDANA-NSS nuisance spaces on the same full-length canonical fMRIPrep BOLD using task-independent residual QC.
- Inputs: Sentinel manifest, canonical non-echo MNI fMRIPrep BOLD/masks/confounds, and completed matched `full-fastica` and `nss-fastica` audit derivatives.
- Outputs: Tracked run, pair, summary, figure, report, and provenance files under `qc/tedana_audit/nuisance_qc`; residual arrays remain in memory.
- Typical command: `"$AUDIT_PYTHON" audit_tedana_nuisance_qc.py build --overwrite`; preview with `build --dry-run`.
- Checker: `"$AUDIT_PYTHON" audit_tedana_nuisance_qc.py check` validates exact condition coverage, manifest checksum, and output checksums.
- Notes: Metrics are evaluated on N:T. The NSS matrix has exactly N leading zero rows while fMRIPrep NSS spikes remain in BASE. N=0 FULL/NSS residuals must agree within the benchmark's tight floating-point tolerance (`rtol=1e-6`, `atol=1e-8`); failures report maximum absolute difference and normalized RMSE. These are nuisance-model QC comparisons, not reproductions of the simultaneous production task GLM.

### `audit_tedana_l1_design.py`
- Status: Audit-only; runs `feat_model` but never FEAT.
- Purpose: Measure rank, residual DF, condition number, task-EV nuisance R-squared/VIF, task-subspace overlap, and canonical contrast efficiency for BASE, TEDANA-FULL, and TEDANA-NSS in actual rendered RF1 first-level designs.
- Inputs: Sentinel manifest, matched benchmark mixing/metrics, four downstream task repositories and their canonical activation inputs, and FSL `feat_model`.
- Outputs: Audit-only task EVs, source FSFs, and copied FSFs/matrices under `derivatives/tedana-audit/l1-design`, plus tracked tables/report/provenance under `qc/tedana_audit/l1_design`.
- Typical command: `"$AUDIT_PYTHON" audit_tedana_l1_design.py build --render-missing --overwrite`; preview with `build --dry-run`.
- Checker: `"$AUDIT_PYTHON" audit_tedana_l1_design.py check` validates three-condition coverage, sentinel checksum, and output checksums.
- Notes: `--render-missing` regenerates canonical task EVs from BIDS events and invokes the downstream `L1stats.sh --render-only` activation workers inside an audit-only derivative root. It records source FSFs in `source_fsfs.tsv`, never runs FEAT, and never writes to a downstream repository. The canonical fMRIPrep BOLD supplies only TR and volume count during rendering. Only output and confound paths are replaced in final audit copies. The script verifies that canonical template high-pass filtering is disabled, never examines task-effect magnitude, and fits task and nuisance columns simultaneously. Add `--include-ppi` only for a reviewed targeted extension.

### `audit_tedana_scanner_era.py`
- Status: Read-only forensic audit.
- Purpose: Separate protocol metadata from reconstructed-image/noise properties across E11, XA30, and XA60; compare PCA/MAPCA behavior; form within-subject cross-era pairs; and inventory representative raw DICOM headers without identifiers or dates.
- Inputs: Full `current_runs.tsv`, BIDS echo sidecars, fMRIPrep echo-wise inputs/masks/confounds, TEDANA PCA/MAPCA outputs, and private source DICOMs when available.
- Outputs: Tracked protocol summary and within-era exception tables, echo/run properties, within-subject pairs, privacy-filtered DICOM summaries, report, and provenance under `qc/tedana_audit/scanner_era`.
- Typical command: `"$AUDIT_PYTHON" audit_tedana_scanner_era.py build --jobs 4 --overwrite`; preview with `build --dry-run`.
- Checker: `"$AUDIT_PYTHON" audit_tedana_scanner_era.py check` validates current-run identity and output checksums.
- Notes: Cross-era differences are observational. A missing BIDS field is not invariant. Raw-header extraction requires the version of `pydicom` pinned in `requirements-tedana-audit.txt`; install it into `AUDIT_PYTHON` using pip's `--no-deps` option as shown in the audit runbook. The tracked raw-header summary uses an explicit scientific-keyword allowlist and omits private tags, free text, identifiers, UIDs, dates, timestamps, and raw DICOM paths while retaining scientific timing fields such as EchoTime. `--skip-dicom-headers` is an explicit incomplete fallback, not the final forensic pass.

### `audit_tedana_seed_stability.py`
- Status: Audit-only selection and summary workflow.
- Purpose: Select twelve deterministic cross-era/rank/dimensionality/motion cases and compare prespecified FastICA seeds without matching component numbering.
- Inputs: Current cohort inventory, refreshed design burden, canonical BOLD/confounds, and completed seed benchmark configurations from `benchmark_tedana.py`.
- Outputs: Tracked seed manifest under `qc/tedana_audit/seeds` and run/pair/summary/report/provenance files under `qc/tedana_audit/seed_stability`.
- Typical command: `"$AUDIT_PYTHON" audit_tedana_seed_stability.py select --overwrite`, followed after benchmark completion by `build --overwrite`.
- Checker: `"$AUDIT_PYTHON" audit_tedana_seed_stability.py check` validates five seeds per selected run, manifest identity, and output checksums.
- Notes: Comparison targets classification burden, independent nuisance rank, and nuisance-adjusted data/QC against seed 42. No component-number correspondence is assumed, no residual image is written, and production should reconsider RobustICA only if FastICA seed changes are scientifically consequential.

### `build_tedana_final_report.py`
- Status: Decision synthesis; read-only with respect to production data.
- Purpose: Build the final decision-facing report only after burden, scanner-era, nuisance-QC, canonical-design, seed-stability, and T2*/optcom evidence tables exist.
- Inputs: Validated tracked tables under `qc/tedana_audit`.
- Outputs: `qc/tedana_audit/final_report.md` and checksum provenance.
- Typical command: `"$AUDIT_PYTHON" build_tedana_final_report.py build --dry-run`, then `build` after every input is present.
- Checker: `"$AUDIT_PYTHON" build_tedana_final_report.py check` validates every input and the report checksum.
- Notes: The report explicitly documents RF1's simultaneous task-plus-nuisance FEAT architecture. It cannot authorize a production change and does not introduce aggressive/non-aggressive/tedort comparisons or production BOLD residualization.

### `summarize_tedana_dimensionality.py`
- Status: Read-only matched sentinel interpretation gate; not production processing.
- Purpose: Isolate NSS effects with matched FULL-FastICA versus NSS-FastICA, distinguish PCA-selected from final ICA counts, and quantify RobustICA count changes after an identical PCA step.
- Inputs: Sentinel manifest, historical TEDANA tables, and completed `full-fastica`, `nss-fastica`, and `nss-robustica` audit derivatives.
- Outputs: Tracked paired/review TSVs, figure, report, and provenance under `qc/tedana_audit/dimensionality`.
- Typical command: `"$AUDIT_PYTHON" summarize_tedana_dimensionality.py build --overwrite`; preview with `build --dry-run`.
- Checker: `"$AUDIT_PYTHON" summarize_tedana_dimensionality.py check` validates exact coverage, PCA-contract identity, live inputs, checksums, and exact NSS=0 output identity.
- Notes: Historical versus FULL-FastICA remains descriptive because the mask contract differs. Only FULL-FastICA versus NSS-FastICA isolates dummy-scan handling. RobustICA may return fewer stable ICA components than the shared PCA count; that is not evidence that RobustICA changed or repaired PCA.

### `summarize_tedana_pca_methods.py`
- Status: Read-only targeted PCA-criterion interpretation gate; not production processing.
- Purpose: Compare matched NSS-aware FastICA runs using AIC, KIC, and MDL across model order, classification, exact nuisance rank, residual degrees of freedom, denoising proxies, motion coupling, and image similarity without claiming a gold-standard clean series.
- Inputs: `qc/tedana_audit/design/pca_method_benchmark.tsv`, completed `nss-fastica`, `nss-kic-fastica`, and `nss-mdl-fastica` audit derivatives, fMRIPrep masks/confounds, and zero-padded full-grid ICA mixing matrices.
- Outputs: Tracked method/pair TSVs, component-review manifest, figure, report, and provenance under `qc/tedana_audit/pca_methods`.
- Typical command: `"$AUDIT_PYTHON" summarize_tedana_pca_methods.py build --overwrite`; preview with `build --dry-run`.
- Checker: `"$AUDIT_PYTHON" summarize_tedana_pca_methods.py check` validates exact coverage, output checksums, the target manifest, and the live benchmark-input inventory.
- Notes: Optimally combined inputs must be exactly identical across criteria. No winner is selected from tSNR, DVARS, component count, or rank alone; interpretation requires convergent artifact attenuation, signal preservation, design cost, and component review.

### `summarize_tedana_benchmark.py`
- Status: Read-only sentinel comparison and interpretation gate; not production processing.
- Purpose: Build paired T2*/optimal-combination, historical/FastICA/RobustICA, and steady-state denoising summaries plus a focused component-review manifest.
- Inputs: `qc/tedana_audit/sentinel_runs.tsv`, completed four-configuration outputs under `derivatives/tedana-audit/benchmark`, and the sentinel fMRIPrep masks/confounds.
- Outputs: Tracked TSVs, figures, report, and provenance under `qc/tedana_audit/benchmark`.
- Typical command: `"$AUDIT_PYTHON" summarize_tedana_benchmark.py build --overwrite`; preview with `build --dry-run`.
- Checker: `"$AUDIT_PYTHON" summarize_tedana_benchmark.py check` verifies input provenance, output checksums, exact run identities, finite metrics, and row counts.
- Notes: The two `NSS=0` T2S configurations must be numerically identical and fail closed otherwise. Raw T2* Pearson correlation is retained alongside log-scale Pearson, rank correlation, and voxelwise percent-difference summaries because sparse extreme fits can dominate the raw statistic. Denoising metrics use only steady-state volumes. Motion24 is fitted only to the denoised global signal in this stage; it does not alter classifications. Report and component-figure paths are validated when present. The report is descriptive and cannot by itself modify production TEDANA, confounds, or QC policy.

### `summarize_tedana_motion.py`
- Status: Read-only Motion24 interpretation gate; not production processing.
- Purpose: Verify classification identity, collect TEDANA-native Motion24 R-squared/F/p metrics, summarize them by run/task/classification, and select focused component-review candidates.
- Inputs: `qc/tedana_audit/sentinel_runs.tsv` plus completed ordinary and Motion24 FastICA/RobustICA outputs under `derivatives/tedana-audit/benchmark`.
- Outputs: An ignored component table at `derivatives/tedana-audit/motion24_components.tsv` and tracked summaries, figures, review manifest, report, and provenance under `qc/tedana_audit/motion`.
- Typical command: `"$AUDIT_PYTHON" summarize_tedana_motion.py build --overwrite`; preview with `build --dry-run`.
- Checker: `"$AUDIT_PYTHON" summarize_tedana_motion.py check` verifies exact sentinel/configuration coverage, classification identity, live-input provenance, and output checksums.
- Notes: Motion24 does not participate in any decision node. R-squared values of 0.10, 0.25, and 0.50 are descriptive summaries only. The review manifest prioritizes accepted high-motion, rejected low-motion, and high-variance rejected components; human review is required before any policy change.

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
- Purpose: Report missing imaging/behavioral BIDS outputs, unshifted `scans.tsv` files, and events relationship failures.
- Inputs: Subject list, BIDS tree, source DICOMs, and private behavior root.
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
- Status: Provenance-only legacy helper.
- Purpose: Document the historical Social Doors/Doors source mapping and behavioral-validity logic ported to `convert_behavior.py`.
- Inputs: Task event sources and `sublist-new.txt`.
- Outputs: BIDS event TSV files.
- Typical command: do not use for new production conversion; use `run_convert_behavior.sh`.
- Checker: `check_events.py` covers the production Python implementation.
- Notes: Retained as provenance. It handles both sessions but silently chose the first source candidate; the production converter treats multiple candidates as an ambiguity error.

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
GEOMETRY_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
GEOMETRY_PREFIX=../logs/geometry/fmriprep-geometry-$(date +%Y%m%d-%H%M%S)
AUDIT_JSON="${GEOMETRY_PREFIX}.json"
AUDIT_TSV="${GEOMETRY_PREFIX}.tsv"

bash run_prepdata.sh --sublist "$SUBLIST" --jobs "$PREP_JOBS" --dry-run
bash run_mriqc.sh --sublist "$SUBLIST" --jobs "$MRIQC_JOBS" --dry-run
bash run_warpkit.sh --sublist "$SUBLIST" --jobs "$WARPKIT_JOBS" --dry-run
python3 addIntendedFor.py --sublist "$SUBLIST" --dry-run
bash run_fmriprep.sh --sublist "$SUBLIST" --jobs "$FMRIPREP_JOBS" --dry-run
"$GEOMETRY_PYTHON" fmriprep_geometry.py audit --report-prefix "$GEOMETRY_PREFIX"
"$GEOMETRY_PYTHON" fmriprep_geometry.py repair --audit-json "$AUDIT_JSON"
bash run_tedana.sh --sublist "$SUBLIST" --jobs "$TEDANA_JOBS" --dry-run
python3 genTedanaConfounds.py --sublist "$SUBLIST" --dry-run
```

Remove `--dry-run` after reviewing the planned commands. Use `--sublist FILE`
only for an exceptional review, recovery run, or intentionally separate
validation list.

The geometry audit is always cohort-wide and is required after fMRIPrep,
including for a from-scratch rerun. Review `AUDIT_TSV` and the repair preview.
If there are reviewed outliers, apply the frozen plan with
`"$GEOMETRY_PYTHON" fmriprep_geometry.py repair --audit-json "$AUDIT_JSON"
--apply`; if there are no outliers, do not run `--apply`. In either case, do
not advance to downstream analysis-manifest construction until the geometry
checker below prints `CHECK PASSED`.

After each real stage, run the corresponding completion check:

```bash
bash check_bids.sh --sublist "$SUBLIST"
bash check_mriqc.sh --sublist "$SUBLIST"
bash check_warpkit.sh --sublist "$SUBLIST"
bash check_fmriprep.sh --sublist "$SUBLIST"
"$GEOMETRY_PYTHON" fmriprep_geometry.py verify --audit-json "$AUDIT_JSON"
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
| PyDeface | `/ZPOOL/data/tools/anaconda/tug87422/envs/pydeface-2.1/bin/pydeface` |
| MRIQC | `/ZPOOL/data/tools/mriqc-24.0.2.simg` |
| fMRIPrep | `/ZPOOL/data/tools/fmriprep-25.2.5.simg` |
| Warpkit | `/ZPOOL/data/tools/anaconda/tug87422/envs/warpkit-1.4.0/bin/wk-medic`; legacy fallback `/ZPOOL/data/tools/warpkit.sif` |
| TemplateFlow | `/ZPOOL/data/tools/templateflow` |
| FreeSurfer license | `/ZPOOL/data/tools/licenses/fs_license.txt` |

## Choosing `--jobs`

Start with the defaults unless Linux2 is busy or a stage is being debugged:
predata uses 6 subject/session jobs, MRIQC uses 8 subject/session jobs,
Warpkit uses 8 subject/session/task/run jobs, fMRIPrep uses 2 subject jobs, and
TEDANA uses 8 subject jobs. Each wrapper prints its subject list and job plan
before launching.

Each MRIQC session is capped at `MRIQC_NPROCS=8`,
`MRIQC_OMP_NTHREADS=4`, and `MRIQC_MEM_GB=20` unless those environment
variables are overridden. These limits prevent every container from
auto-detecting all processors on Linux2 when several sessions run together.

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
`prepdata.sh` runs HeuDiConv, behavior conversion, defacing, date shifting, and
events validation in scratch. Only after those checks pass does it remove the
existing live BIDS session and move the staged session into place. Matching
existing events are copied into the stage first and refreshed when source logs
are available, so an imaging overwrite cannot silently erase curated events.

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
expected multi-echo task files, a defaced T1w, and shifted `scans.tsv`. A
subject without any BIDS T1w is reported as blocked before fMRIPrep/FreeSurfer;
inspect the source scan and heuristic before rerunning conversion. Predata must
not alter raw DICOM source data.

Warpkit normally requires all four magnitude NIfTIs, phase NIfTIs, and phase
JSON files before launch. A target listed in `warpkit_reuse.tsv` instead
requires all four target magnitude echoes plus the completed source-run
fieldmap. It writes a run-specific magnitude reference, copied fieldmap with
explicit reuse metadata, provenance JSON, and completion marker. No unlisted
run may bypass the normal phase-input requirement.

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

The post-fMRIPrep geometry audit is a cohort-wide scientific-validity gate,
not a subject-completion shortcut. It inventories every non-echo volumetric
`MNI152NLin6Asym` preprocessed BOLD, so never replace it with a tiny validation
or new-batch list. A reviewed repair preserves originals and provenance outside
the fMRIPrep tree while placing validated corrected images back at their
existing canonical fMRIPrep paths. Pristine BIDS data are not repair inputs and
must remain unchanged.

`genTedanaConfounds.py --sublist FILE` then builds FSL-ready confound TSVs only
for TEDANA metric files matching that subject list. These checks and generated
tables are operational completion products, not scientific validation.

## Full-Cohort Imaging QC

Run group MRIQC only after the full participant batch completes participant
MRIQC. Build run imaging QC only after MRIQC, TEDANA, and the post-fMRIPrep
geometry gate are complete. This is a cohort-level scientific stage, not a
routine new-subject validation requirement.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash mriqc_group.sh --dry-run
bash mriqc_group.sh
QC_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
"$QC_PYTHON" -c 'import numpy, pandas, nibabel, scipy, matplotlib, openpyxl'
"$QC_PYTHON" build_run_qc.py build --dry-run
STAMP=run-qc-$(date +%Y%m%d-%H%M%S)
bash run_logged.sh --label "$STAMP" --include-full-log -- \
  "$QC_PYTHON" build_run_qc.py build \
  --check "$QC_PYTHON" build_run_qc.py check
```

The builder discovers the complete acquired BIDS run inventory rather than
accepting a mutable subject list. It writes all canonical outputs under
`qc/`; use `build --overwrite` only after reviewing existing tracked results.
The checker recomputes source metrics, inventory coverage, thresholds, flags,
paired Social Doors rows, and workbook row sets. It exits nonzero for any
incomplete run. Review the four histograms and Git diffs before committing.
The full summary is small enough to retain in the tracked Markdown run record;
the duplicate raw log remains ignored.

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
18. Defer `mriqc_group.sh`, `build_run_qc.py`, and run imaging-outlier review
   until the full participant batch and required derivatives are complete.
19. Run `make test`.
20. Document the commit SHA tested, subjects/sessions tested, stages tested,
   pass/fail result, and discrepancies.

## Still To Confirm

The scanner-upgrade cutoff needs Linux2 confirmation. The code has used
March 4, 2025; comments historically said March 18, 2025. This branch preserves
the March 4 behavior until Jacob confirms otherwise.
