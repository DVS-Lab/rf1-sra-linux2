# TUBRIC QA: RF1 Validation Report

These are **RF1 study results**, not demonstration data for the reusable
[TUBRIC QA package](https://github.com/DVS-Lab/tubric-qa).
The package repository contains software, tests, documentation and a synthetic
preview only. No RF1 report was published there.

## Plots

The simplified report contains 34 figures: smoothness, tSNR and mean FD for
each functional group, and smoothness only for anatomy. Each echo remains a
separate image. The echo-2 plots correspond to the representative echo used
by our canonical QC:

| Task | Session 01 | Session 02 |
| --- | --- | --- |
| Doors | [Plot](figures/group-e64943e063a7-page-1.png) | [Plot](figures/group-10f4514f26cc-page-1.png) |
| Social Doors | [Plot](figures/group-9e706811be66-page-1.png) | [Plot](figures/group-7b594d8993a9-page-1.png) |
| UGR | [Plot](figures/group-d6ab7b4b5352-page-1.png) | [Plot](figures/group-1953a7a48679-page-1.png) |
| Shared Reward | [Plot](figures/group-e92b47495998-page-1.png) | Not acquired |
| Trust | [Plot](figures/group-6647ebcd26e0-page-1.png) | Not acquired |

[All figures](figures/) and [HTML dashboard](index.html) are included. GitHub
previews the PNGs, but displays HTML as source. Download this whole directory
and open index.html to use the offline dashboard and its table links.

## Verification On 2026-10-26

- Replot completed in 19.6 seconds, with command and check exit codes zero.
  It reused saved tables without indexing BIDS/MRIQC or recomputing QC flags.
- All 2,786 canonical run rows match exactly for tSNR, mean FD and mean
  directional MRIQC FWHM in mm. There are zero tSNR/FD flag disagreements.
- All published artifacts were independently checked against their recorded
  SHA256 hashes. The HTML was initially ignored by RF1's broad `*.html` rule;
  it has been restored byte-for-byte against the original recorded hash,
  with a narrow ignore exception for this dashboard.
- The scanner-era pattern agrees with existing raw-input MRIQC plots. Across
  session-01 tasks, echo-2 median smoothness is approximately 6.95-6.98 mm
  for E11, 8.11-8.16 mm for XA30, and 10.46-10.53 mm for XA60. These are NOT
  the AFNI before/after 6-mm fMRIPrep measurements. Session-02 XA30 comparisons
  have only one or two observations per task and are descriptive only.

## Inventory Reconciliation

The generic report inventories 2,799 BOLD runs at each of four magnitude
echoes, all with matching MRIQC results (11,196 matches). Our canonical QC
contains 2,786 runs. The extra 13 are already source-excluded: five runs for
11753 and eight for 11836. Their presence in a generic inventory does not
reinstate them. Preserve the existing RF1 decisions and analysis handoffs.

The report's 396 missing MRIQC matches are **all anatomical T1w images**:
357 session-01 and 39 session-02 entries. Our production `code/mriqc.sh`
explicitly runs `--modalities bold`. Therefore this is missing anatomical IQM
coverage in an all-modalities report, not missing functional processing.
Do not rerun functional MRIQC. A future functional-only report can use the
existing task filters; anatomical IQMs would require a separately chosen
anatomical MRIQC run. The broad snapshot's completeness status remains false
and is not silently relabeled as a complete anatomical QC assessment.

The four identity/metadata issues are **two duplicate anatomical identities**:
11982 and 12038 each have both `ses-01_T1w.nii` and `ses-01_T1w.nii.gz`.
They are not scanner-software metadata conflicts. Equality of their actual
decompressed contents has not yet been verified on Linux2. Use the read-only
command below; it does not remove files. If identical, the extra uncompressed
copy can subsequently be archived outside BIDS with provenance. If different,
keep both pending source review. No fMRI reprocessing is implied by this check.

```bash
python3 code/reconcile_tubric_qa.py --project "$PWD" --check-anatomy
```

Without `--check-anatomy`, this command verifies the saved report and repeats
the canonical-table comparison without requiring imaging files.

## Scope

This report is a QC inventory, not a selected-participant or exclusion list.
Supplementary metrics remain in tables, and their flags contribute to the
overall flag count even though only three metrics are plotted. Generic
thresholds can differ slightly because the raw inventory includes source-
excluded participants. Canonical RF1 QC and settled decisions remain authoritative.
The replot preserved the original validation findings and input lineage;
live inputs were not rechecked by the presentation-only refresh.
