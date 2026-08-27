# TEDANA Dimensionality And Design-Burden Audit

This is a read-only scientific audit. It does not change production TEDANA, fMRIPrep, confound files, classifications, or analysis exclusions.

## Coverage

- Inventory rows: 2741
- Complete design audits: 2737
- Incomplete design audits: 4
- Existing combined-confound files differing from exact reconstruction: 0

## Prespecified Descriptive Flags

- PCA components greater than half the steady-state time points: 14
- AIC-selected PCA explaining more than 98% of variance: 1
- At least 75 rejected TEDANA components: 35
- Combined nuisance rank at least 30% of original volumes: 121
- Fewer than 100 residual degrees of freedom before task regressors: 1

The first two flags follow TEDANA 26.0.3 documentation as warning signs for unexpectedly high PCA dimensionality. The other thresholds describe RF1 design burden; they are review triggers, not automatic exclusions.

## Interpretation

`combined_rank_with_intercept` is the numerical rank of the exact production nuisance matrix plus a constant. `residual_df_before_task` subtracts that rank from the number of acquired volumes; task regressors and any additional contrasts will consume further degrees of freedom. Column count is also reported because it affects model size, but rank is the relevant estimability quantity.

AIC, KIC, and MDL counts are taken from each completed TEDANA run's saved MAPCA cross-component JSON. They permit a cohort-wide comparison of dimensionality criteria without rerunning ICA. Actual KIC/MDL denoising must still be benchmarked on the generated targeted manifest before any production decision.

## Decision Gate

Review `review_runs.tsv`, the scanner summary, and the targeted `pca_method_benchmark.tsv`. Do not alter production TEDANA or confound construction solely because a run crosses one descriptive threshold. A production change requires matched NSS results, targeted KIC/MDL denoising QC, task-model rank review, and human component inspection.
