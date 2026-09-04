# RF1-SRA Run-Level Imaging QC

This directory is the authoritative, Git-tracked home for cohort-level
run-quality metrics and imaging-QC decisions. The machine-readable source of
truth is `run_qc.tsv`; spreadsheets are regenerated human-facing views.

The production stage runs only after participant MRIQC, fMRIPrep geometry
verification, and TEDANA are complete. It inventories acquired BIDS echo-2
magnitude runs and never manufactures expected-but-unacquired runs. Missing or
ambiguous derivatives produce `qc_status=incomplete`, never an implicit pass or
zero-valued metric.

## Policy

`qc_policy.json` defines four paradigm distributions and four one-sided Tukey
rules. `task-socialdoors` and `task-doors` remain distinct BIDS tasks but are
pooled into the `socialdoors` paradigm for threshold estimation. Thresholds
are calculated once from every finite value for that metric using linear
quartile interpolation and an IQR multiplier of 1.5.

The metrics are:

| Metric | Poor-quality direction | Source |
| --- | --- | --- |
| `tsnr` | below lower fence | MRIQC echo-2 part-mag JSON |
| `fd_mean` | above upper fence | same MRIQC JSON |
| `tedana_rejected_components` | above upper fence | TEDANA final ICA classification |
| `brain_coverage_pct` | below lower fence | fMRIPrep MNI run mask versus fixed target |

The coverage target is generated deterministically from the TemplateFlow
`MNI152NLin6Asym` resolution-02 brain mask after removing the historical
Shared Reward cerebellum/brainstem mask preserved in `reference/`. That mask
comes from `DVS-Lab/sharedreward-aging:masks/cerebellum-brainstem_mask.nii.gz`
and is pinned by SHA-256 in `qc_policy.json`. Both source checksums, the
generated target checksum, voxel counts, derivative software metadata, package
versions, and generation time are recorded in
`provenance.json`. Coverage is intersection divided by target-mask voxels, not
Dice and not a FEAT-mask voxel-count ratio. When grids differ, the fixed target
is resampled onto the run-mask grid with nearest-neighbor interpolation before
the intersection and denominator are counted.

## Outputs

```text
qc/
  run_qc.tsv
  thresholds.tsv
  socialdoors_pair_qc.tsv
  provenance.json
  reference/rf1-sra_MNI152NLin6Asym_desc-qctarget_mask.nii.gz
  spreadsheets/{sharedreward,trust,ugr,socialdoors}_qc.xlsx
  figures/{sharedreward,trust,ugr,socialdoors}_histograms.png
  scanner_era/
    run_metrics.tsv
    summary.tsv
    report.md
    provenance.json
    figures/{sharedreward,trust,ugr,socialdoors}_by_scanner_era.png
```

The paired Social Doors table describes both run states and whether either run
is an imaging outlier. It deliberately contains no generic subject-exclusion
field; downstream analyses decide whether their contrast requires both runs.

## Production Command

Run with the shared TEDANA environment, which supplies pandas, nibabel, scipy,
matplotlib, and openpyxl:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code
QC_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python

"$QC_PYTHON" -c 'import numpy, pandas, nibabel, scipy, matplotlib, openpyxl'
"$QC_PYTHON" build_run_qc.py build --dry-run

STAMP=run-qc-$(date +%Y%m%d-%H%M%S)
bash run_logged.sh --label "$STAMP" --include-full-log -- \
  "$QC_PYTHON" build_run_qc.py build \
  --check "$QC_PYTHON" build_run_qc.py check
```

If the import check reports that `openpyxl` is missing from this dedicated
environment, install it with
`"$QC_PYTHON" -m pip install 'openpyxl>=3.1,<4'` before rerunning. The logged
production command preserves the concise full cohort summary in a tracked
`logs/records/*.md` file while keeping the duplicate raw log ignored under
`logs/runs/`.

Regenerating existing canonical outputs requires `build --overwrite`. Review
the Git diff in all TSV/JSON files and the four figures before committing.
Incomplete runs make the checker fail but do not prevent the builder from
reporting and writing the rest of the cohort. After review, add both `qc/` and
the new `logs/records/*.md` file to the same Git commit.

Do not edit the spreadsheets manually. Do not combine behavioral exclusions
with this imaging table. Downstream code should join on
`subject + session + task + run` and inspect both `qc_status` and
`imaging_qc_outlier`.

## Scanner-Era Extension

`build_scanner_era_qc.py` joins the canonical run table to the
`SoftwareVersions` field in each BIDS echo-2 magnitude sidecar and recognizes
only `E11`, `XA30`, and `XA60`. Missing, ambiguous, or unknown era metadata is a
hard error. No raw DICOM headers, dates, private tags, or UID values are read or
tracked.

The four figures show run-level boxplots and all observed values by era for the
same four canonical metrics. Existing pooled cohort fences are overlaid; no
era-specific thresholds or exclusions are calculated. The tracked summary
contains sample sizes, means, standard deviations, quartiles, ranges, pooled
fence flag rates, and median differences from E11. Scanner era is confounded
with acquisition time and cohort composition, so these outputs are descriptive.
Follow large differences with task/session-stratified and, where possible,
within-subject review before making a causal claim.

```bash
"$QC_PYTHON" build_scanner_era_qc.py build --dry-run

STAMP=scanner-era-qc-$(date +%Y%m%d-%H%M%S)
bash run_logged.sh --label "$STAMP" --include-full-log -- \
  "$QC_PYTHON" build_scanner_era_qc.py build \
  --check "$QC_PYTHON" build_scanner_era_qc.py check
```

Regenerating an existing report requires `build --overwrite`. The checker
verifies the canonical-QC and threshold hashes, every BIDS sidecar, all tables,
and every output checksum.
