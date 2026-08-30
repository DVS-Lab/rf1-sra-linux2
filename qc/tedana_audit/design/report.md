# TEDANA Dimensionality And Design-Burden Audit

This is a read-only scientific audit. It does not change production TEDANA, fMRIPrep, confound files, classifications, or analysis exclusions.

## Coverage

- Inventory rows: 2749
- Complete design audits: 2749
- Incomplete design audits: 0
- Existing combined-confound files differing from exact reconstruction: 0

## Prespecified Descriptive Flags

- PCA components greater than half the steady-state time points: 14
- AIC-selected PCA explaining more than 98% of variance: 1
- At least 75 rejected TEDANA components: 35
- Combined nuisance rank at least 30% of original volumes: 121
- Fewer than 100 residual degrees of freedom before task regressors: 1

The first two flags follow TEDANA 26.0.3 documentation as warning signs for unexpectedly high PCA dimensionality. The other thresholds describe RF1 design burden; they are review triggers, not automatic exclusions.

## Interpretation

`tedana_incremental_rank` is the numerical rank of the exact BASE + rejected-ICA nuisance matrix minus the rank of BASE alone. This is the independent statistical cost attributable to TEDANA; raw rejected-component count remains descriptive only.
The cohort median incremental TEDANA rank fraction is 0.050980392156862744; its 95th percentile is 0.20392156862745098.
Rejected-on-accepted cross-component variance is available for 2742/2749 complete runs and is descriptive QC, not evidence of pre-GLM signal removal.
`combined_rank_with_intercept` is the numerical rank of the exact production nuisance matrix plus a constant. `residual_df_before_task` subtracts that rank from the number of acquired volumes; actual task regressors and PPI/nPPI regressors consume additional degrees of freedom. Column count is reported because it affects model size, but rank is the relevant estimability quantity.

AIC, KIC, and MDL counts are taken from each completed TEDANA run's saved MAPCA cross-component JSON. They permit a cohort-wide comparison of dimensionality criteria without rerunning ICA. Actual KIC/MDL denoising must still be benchmarked on the generated targeted manifest before any production decision.

## Decision Gate

Review `extreme_tail_runs.tsv`, the grouped burden summaries, and the targeted `pca_method_benchmark.tsv`. The p99 tail labels are descriptive review triggers, never automatic exclusions. The production RF1 analysis fits task and nuisance EVs simultaneously; no pre-regressed or residualized BOLD is created by this audit.
