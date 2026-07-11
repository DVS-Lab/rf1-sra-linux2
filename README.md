# RF1-SRA Linux2 fMRI Preprocessing

This repository contains the Smith Lab Linux2 preprocessing workflow for RF1-SRA
multi-echo fMRI data from the UGR, Social Doors, Trust, and Shared Reward tasks.
Behavioral task processing lives in separate repositories. This repository is
for MRI data management, BIDS conversion, fieldmap preparation, fMRIPrep,
FreeSurfer/CIFTI derivative generation, TEDANA, MRIQC, downstream confound
generation, and cohort-level metric extraction helpers.

## Scope And Privacy

Raw DICOMs are not stored in GitHub. On Linux2 they live under the lab-controlled
source-data area, normally `/ZPOOL/data/sourcedata/sourcedata/rf1-sra`. BIDS
NIfTI images, fMRIPrep derivatives, TEDANA outputs, MRIQC reports, scheduler
logs, temporary files, generated metrics, and the generated `bids/` tree are
intentionally excluded from version control.

Production processing should occur on Smith Lab Linux2 from the production
checkout:

```bash
/ZPOOL/data/projects/rf1-sra-linux2
```

The scripts derive `PROJECT_ROOT` from the checkout that is running them, so a
separate validation clone can still write to its own `bids/`, `derivatives/`,
and `logs/` trees when one is intentionally created. Do not hard-code one
project root into wrappers or downstream commands.

Do not run destructive production processing from unreviewed local edits. Use
`--dry-run` first, keep logs, and require an explicit operator decision before
using `--overwrite`.

## Relationship To rf1-dwi

This repository is upstream of `rf1-dwi`. Run this fMRI/data-management workflow
first. It creates and maintains the shared BIDS dataset, fMRIPrep derivatives,
FreeSurfer subjects, and fsLR CIFTI outputs that `rf1-dwi` may consume for
QSIPrep/QSIRecon.

`rf1-dwi` should not duplicate BIDS, fMRIPrep, or FreeSurfer outputs. Instead,
point the DWI repo at the production Linux2 checkout for this repo:

```bash
BIDS_ROOT=/ZPOOL/data/projects/rf1-sra-linux2/bids
FMRIPREP_DERIVATIVES_DIR=/ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep
FREESURFER_SUBJECTS_DIR=/ZPOOL/data/projects/rf1-sra-linux2/derivatives/freesurfer
```

Historical validation checkout names are documented in
[validation history](docs/archive/validation-history.md), but they are not the
production defaults.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `code/` | All production entry points, worker scripts, helpers, validation scripts, and the current batch subject list. |
| `bids/` | Generated BIDS dataset on Linux2; ignored by Git. |
| `derivatives/` | Generated outputs are ignored and should not contain repository code. |
| `tests/` | Synthetic pytest coverage for parsing, path generation, safety checks, and completion checks. |

See `code/README.md` for the detailed implementation manual.

## Pipeline Map

The dependency order is:

```text
Raw DICOMs / XNAT
  -> rf1-sra-linux2 BIDS conversion
  -> rf1-sra-linux2 Warpkit / IntendedFor
  -> rf1-sra-linux2 fMRIPrep / FreeSurfer / CIFTI
  -> rf1-sra-linux2 TEDANA / MRIQC / confounds
  -> rf1-sra-linux2 cohort-level MRIQC metrics and outlier review
  -> rf1-dwi QSIPrep / QSIRecon
```

In this repository the modular stages are:

```mermaid
flowchart TD
  A["Download DICOMs from XNAT"] --> B["Convert to BIDS, deface, shift dates"]
  B --> C["Generate Warpkit fieldmaps"]
  C --> D["Repair IntendedFor metadata"]
  D --> E["Run fMRIPrep"]
  E --> F["Run TEDANA"]
  F --> G["Generate TEDANA/FSL confounds"]
  B --> H["Run MRIQC"]
  H --> I["Group MRIQC and cohort QC metrics"]
  E --> J["rf1-dwi consumes shared BIDS/fMRIPrep/FreeSurfer"]
```

## Standard Paths

The shared Linux2 source-data and tool paths are fixed in `code/pipeline_common.sh`.
The project root is derived from the checkout location so a separate validation
clone writes to its own `bids/`, `derivatives/`, and `logs/` directories.

| Item | Path |
| --- | --- |
| Production checkout | `/ZPOOL/data/projects/rf1-sra-linux2` |
| Production BIDS root | `/ZPOOL/data/projects/rf1-sra-linux2/bids` |
| Production fMRIPrep derivatives | `/ZPOOL/data/projects/rf1-sra-linux2/derivatives/fmriprep` |
| Production FreeSurfer subjects | `/ZPOOL/data/projects/rf1-sra-linux2/derivatives/freesurfer` |
| Source DICOMs | `/ZPOOL/data/sourcedata/sourcedata/rf1-sra` |
| Scratch | `/ZPOOL/data/scratch` |
| Tool/container directory | `/ZPOOL/data/tools` |
| TemplateFlow | `/ZPOOL/data/tools/templateflow` |
| FreeSurfer license | `/ZPOOL/data/tools/licenses/fs_license.txt` |

| Tool | Default location/configuration |
| --- | --- |
| HeuDiConv | `/ZPOOL/data/tools/heudiconv-1.4.0.sif` |
| MRIQC | `/ZPOOL/data/tools/mriqc-24.0.2.simg` |
| fMRIPrep | `/ZPOOL/data/tools/fmriprep-25.2.5.simg` |
| Warpkit | Native `wk-medic` from `pip install warpkit`; legacy fallback: `/ZPOOL/data/tools/warpkit.sif` with `WARPKIT_BACKEND=apptainer` |
| TemplateFlow | `/ZPOOL/data/tools/templateflow` |
| FreeSurfer license | `/ZPOOL/data/tools/licenses/fs_license.txt` |

The script comments historically said the scanner-upgrade heuristic cutoff was
March 18, 2025, while the code has used March 4, 2025 since the first Linux2
commit. The production workflow preserves the March 4 behavior until David or
Jacob confirms a scientific correction.

## Subject Lists

Use subject lists in this order:

| Level | Purpose | Normal location |
| --- | --- | --- |
| Full production/cohort list | Run cohort-level MRIQC, metrics, and final completeness checks after all intended participants are present. | Lab-maintained full cohort list for final batch review. |
| New-batch list | Run newly available participants through the modular fMRI/data-management stages. | `code/sublist-new.txt` |
| Small validation list | Validate a workflow change with representative subjects before production use. | Local operator list, commonly under `logs/validation/` |

`code/sublist-new.txt` is the only file operators should normally edit for a
new incoming batch. It is a plain text file with one subject per line. Blank
lines and comments beginning with `#` are ignored, and either `10001` or
`sub-10001` forms are accepted by the wrappers. Scripts should not need edits
for routine new-batch processing.

For a small validation run, keep a separate review-only list and pass it with
`--sublist`:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
mkdir -p logs/validation
printf '10317\n10953\n' > logs/validation/sublist-fmri-validation.txt

cd code
SUBLIST=../logs/validation/sublist-fmri-validation.txt
```

For full-cohort MRIQC and metric review, replace `sublist-new.txt` in the
examples with the lab-maintained full cohort list. Do not make a tiny
validation list or a new-batch list look like the final cohort list.

## Choosing `--jobs`

Start conservatively when the Linux2 load is unknown, then raise `--jobs` only
after the dry-run and the first real subject look healthy. Current defaults are
`run_prepdata.sh --jobs 6`, `run_mriqc.sh --jobs 8`,
`run_warpkit.sh --jobs 8`, `run_fmriprep.sh --jobs 2`, and
`run_tedana.sh --jobs 8`. The wrappers print their job plan before launching.

fMRIPrep is the tightest stage: `run_fmriprep.sh --jobs N` splits a fixed
Linux2 budget of 96 CPU threads and 196000 MB RAM across simultaneous subjects.
Use `--jobs 1` for debugging, keep the default `--jobs 2` for normal production
unless Linux2 is quiet and the operator intentionally raises it, and avoid
mixing high fMRIPrep concurrency with other heavy container stages.

## Everyday Use

Quick start on Linux2:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
vim sublist-new.txt
SUBLIST=sublist-new.txt
PREP_JOBS=6
MRIQC_JOBS=8
WARPKIT_JOBS=8
FMRIPREP_JOBS=2
TEDANA_JOBS=8

python3 downloadXNAT.py

bash run_prepdata.sh --sublist "$SUBLIST" --jobs "$PREP_JOBS" --dry-run
bash run_prepdata.sh --sublist "$SUBLIST" --jobs "$PREP_JOBS"
bash check_bids.sh --sublist "$SUBLIST"

bash run_mriqc.sh --sublist "$SUBLIST" --jobs "$MRIQC_JOBS" --dry-run
bash run_mriqc.sh --sublist "$SUBLIST" --jobs "$MRIQC_JOBS"
bash check_mriqc.sh --sublist "$SUBLIST"

bash run_warpkit.sh --sublist "$SUBLIST" --jobs "$WARPKIT_JOBS" --dry-run
bash run_warpkit.sh --sublist "$SUBLIST" --jobs "$WARPKIT_JOBS"
bash check_warpkit.sh --sublist "$SUBLIST"

python3 addIntendedFor.py --sublist "$SUBLIST" --dry-run
python3 addIntendedFor.py --sublist "$SUBLIST"

bash run_fmriprep.sh --sublist "$SUBLIST" --jobs "$FMRIPREP_JOBS" --dry-run
bash run_fmriprep.sh --sublist "$SUBLIST" --jobs "$FMRIPREP_JOBS"
bash check_fmriprep.sh --sublist "$SUBLIST"

bash run_tedana.sh --sublist "$SUBLIST" --jobs "$TEDANA_JOBS" --dry-run
bash run_tedana.sh --sublist "$SUBLIST" --jobs "$TEDANA_JOBS"
bash check_tedana.sh --sublist "$SUBLIST"

python3 genTedanaConfounds.py --sublist "$SUBLIST" --dry-run
python3 genTedanaConfounds.py --sublist "$SUBLIST"
```

`--dry-run` means print or validate the planned work before launching the heavy
stage. `--sublist FILE` points a wrapper or checker at a review-specific subject
list instead of `code/sublist-new.txt`. `--jobs N` controls how many
subject-level jobs run at once; fMRIPrep also divides its CPU and memory budget
across those jobs.

When changing Warpkit versions or backends, avoid mixing fieldmap provenance:
test one representative run with `warpkit.sh --overwrite`, then rerun
`run_warpkit.sh --overwrite`, `addIntendedFor.py`, and the Warpkit/IntendedFor
checks for the affected subject list before resuming fMRIPrep.

## Sessions And Expected Absences

Many RF1-SRA participants have both `ses-01` and `ses-02`. The production
wrappers try or discover both sessions, and optional missing `ses-02` source
data are reported as skips rather than hidden.

The current task/session rules are intentionally narrow and tested:

| Session | Expected tasks |
| --- | --- |
| `ses-01` | UGR, Trust, Shared Reward, Doors, Social Doors |
| `ses-02` | UGR, Doors, Social Doors |

UGR, Trust, and Shared Reward use runs 1 and 2 when present. Doors and Social
Doors generally lack run 2, so the wrappers and checkers expect run 1 only.
Some participants may intentionally lack a task or run; validation notes should
say whether an absence is expected or requires investigation.

For a small Linux2 validation list, prefer subjects that overlap with the
`rf1-dwi` validation subjects, such as `10317` and `10953`, when they cover
useful fMRI data. Because this repository must validate multi-session behavior,
the validation set should also include at least one `ses-01`, at least one
`ses-02`, at least one intentionally absent task/run, and ideally one
pre-upgrade and one post-upgrade scanner/heuristic case if available. Keep that
validation list under `logs/validation/` or another review-only location; do
not make it a production default unless David asks.

## Advanced: Logged Runs

Use `--dry-run` first for pipeline stages that support it. `prepdata.sh` runs
HeuDiConv into scratch first, validates that a new BIDS session exists there,
and only then touches the live `bids/` tree. MRIQC is a separate restartable
stage run by `run_mriqc.sh`; reconverting BIDS data is not required to rerun
MRIQC. Replacing an existing BIDS session
requires `--overwrite`; the old session is removed immediately before the
validated staged session is moved into place, so `bids/` does not accumulate
non-BIDS backup folders.

Run the matching `check_*.sh` script after each major stage. These scripts end
with `CHECK PASSED` or `CHECK FAILED`, so a terminal transcript or ignored log
file has a clear final answer about operational completion.

For runs that should leave a compact GitHub-visible audit trail, use
`code/run_logged.sh`. It writes the full raw terminal output to ignored
`logs/runs/` and writes a small Markdown record to tracked `logs/records/`.
The `--` marker means `run_logged.sh` options stop and the real command starts.
The optional `--check` marker starts a checker command that runs only after the
main command exits 0. If no check is supplied, the record says `Check exit:
none`; if the main command fails, the check is skipped.

Raw DICOM source directories are treated as immutable by preprocessing scripts.
Localizer directories are reported but no longer moved out of source data.

fMRIPrep skipping now checks for a practical set of expected outputs rather than
only an HTML report and session directory. Current fMRIPrep runs also generate
FreeSurfer subjects under `derivatives/freesurfer` and fsLR CIFTI outputs under
`derivatives/fmriprep` so those derivatives can be reused by a separate DWI
workflow such as QSIPrep/QSIRecon. This is a completion check, not a
scientific-validity guarantee. `run_fmriprep.sh --jobs N` controls how many
subjects run at once and divides the Linux2 fMRIPrep resource budget across
those jobs before passing `--nprocs`, `--omp-nthreads`, and `--mem` into
fMRIPrep. MRIQC, fMRIPrep, TEDANA, fieldmap metadata, and confound outputs
still require visual and scientific review on Linux2.

## Full-Cohort MRIQC

Run cohort-level MRIQC and metric/outlier summaries only after the full
participant batch has completed participant-level MRIQC. Do not use these
summaries as part of routine new-subject validation, because outlier thresholds
are only meaningful when the cohort is present.

The group report follows the same pattern as the R21 resting-state workflow:
participant MRIQC first, group MRIQC second, then run/subject metric summaries
and outlier review.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
bash mriqc_group.sh --dry-run
bash mriqc_group.sh
python3 extract-metrics.py --sublist sublist-new.txt --dry-run
python3 extract-metrics.py --sublist sublist-new.txt
```

Use `extract-metrics.py` at this stage to collect run-level `tsnr` and
`fd_mean` from completed MRIQC JSON files; replace `sublist-new.txt` with the
final cohort subject list if that list lives somewhere else. Any run or subject
outlier decisions should be documented with the group MRIQC outputs and
reviewed scientifically; they are not automatic per-batch exclusions.

## How To Know Whether It Worked

Look for these signals:

- `Command exit: 0` means the main command finished successfully.
- `Check exit: 0` means the checker command passed.
- `Check exit: none` means no checker was provided.
- `Check exit: skipped` means the main command failed, so output validation did
  not run.
- `CHECK PASSED` is the clearest phrase to search for at the end of a checker
  log or compact run record.
- `CHECK FAILED` means expected operational outputs are incomplete; inspect the
  newest Markdown record under `logs/records/`, then the matching raw log under
  `logs/runs/`.

## Before Asking For Help

When asking David or Jacob for help, send the command, the newest
`logs/records/*.md` file, whether `Command exit` and `Check exit` are 0, the
first `CHECK FAILED` or error line, and whether the case was expected to have
`ses-01`, `ses-02`, and the task/run being checked.

## More Details

- [Code manual](code/README.md)
- [Validation history](docs/archive/validation-history.md)

Repository-level checks do not require real imaging data or neuroimaging
containers:

```bash
make test
```

The test command runs shell syntax checks, optional ShellCheck for active
scripts, Python compilation, synthetic pytest tests, JSON parsing, README path
validation, and a small temporary-file hygiene check.

## Development Workflow

Keep production changes small and coherent. For ordinary development, create a
branch from `origin/main`, commit focused changes, push the branch, and open a
pull request. When maintainers intentionally work directly on `main`, use the
same discipline: inspect the diff, run `make test`, and push only reviewed
documentation or code changes.

Historical repository size may still reflect previously tracked derivatives and
logs. Current generated imaging outputs stay ignored. Any history rewrite would
need a separate, coordinated `git filter-repo` plan.

## Outside Users And OpenNeuro

The README previously contained placeholder DataLad/OpenNeuro reproduction
commands. Outside-user reproduction is not currently documented end-to-end here.
Do not rely on those removed placeholders for public reproduction until the
OpenNeuro dataset identifier and instructions are confirmed.

## Citation And Acknowledgments

More project context appears in Smith et al., 2024, Data in Brief:
https://doi.org/10.1016/j.dib.2024.110810

This work was supported, in part, by grants from the National Institutes of
Health.
