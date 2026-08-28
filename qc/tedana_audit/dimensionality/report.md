# Matched TEDANA Dimensionality Report

This report is audit evidence, not a production-method decision.

## Design

- Sentinel runs: 51
- NSS=0 exact controls: 11
- FULL-FastICA and NSS-FastICA use identical fMRIPrep echoes, explicit native mask, curvefit, AIC, seed 42, `tedana_orig`, and FastICA. Only `--dummy-scans 0` versus the validated run-specific NSS count differs.
- NSS-FastICA and NSS-RobustICA have an identical PCA contract. Their final ICA count can differ because RobustICA clusters stable components after the shared PCA step.
- Historical production versus FULL-FastICA remains descriptive because the historical command did not explicitly pass the same fMRIPrep mask.

## Matched NSS Effect

- NSS-aware minus full PCA count: 0.00 (IQR -1.00 to 0.00)
- NSS-aware minus full rejected count: 0.00 (IQR -2.00 to 1.00)
- Runs with absolute PCA-count change >=5: 3
- Runs with absolute rejected-count change >=5: 12

## RobustICA Effect After Matched PCA

- RobustICA minus FastICA final ICA count: -3.00 (IQR -6.00 to -1.00)
- RobustICA minus FastICA rejected count: -2.00 (IQR -5.00 to 0.00)
- Runs with absolute final-count change >=10: 10
- Runs with absolute rejected-count change >=10: 6

## Interpretation Gate

Use `paired_dimensionality.tsv` together with the cohort design-burden audit, denoising QC, Motion24 audit, and component review. If matched NSS handling materially changes PCA counts, the report contains a reproducible versioned test case for upstream discussion. If it does not, investigate scanner-era signal properties and PCA criterion choice rather than attributing high dimensionality to NSS handling.
