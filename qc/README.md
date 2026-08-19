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

"$QC_PYTHON" build_run_qc.py build --dry-run
"$QC_PYTHON" build_run_qc.py build
"$QC_PYTHON" build_run_qc.py check
```

Regenerating existing canonical outputs requires `build --overwrite`. Review
the Git diff in all TSV/JSON files and the four figures before committing.
Incomplete runs make the checker fail but do not prevent the builder from
reporting and writing the rest of the cohort.

Do not edit the spreadsheets manually. Do not combine behavioral exclusions
with this imaging table. Downstream code should join on
`subject + session + task + run` and inspect both `qc_status` and
`imaging_qc_outlier`.
