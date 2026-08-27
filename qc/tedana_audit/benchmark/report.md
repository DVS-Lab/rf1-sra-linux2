# TEDANA Sentinel Benchmark Report

This report summarizes isolated audit derivatives. It does not modify or authorize a change to production TEDANA outputs.

## Inventory

- Sentinel runs: 51
- Controlled configurations per run: T2S-FULL, T2S-EXCLUDE-NSS, NSS-aware FastICA, NSS-aware RobustICA.
- N=0 controls: 11
- N=0 numerical identity checks passed: 11

## T2*/Optimal Combination

- T2* median absolute percent difference: 0.0199 (IQR 0.0111 to 0.0324)
- T2* raw spatial correlation: 0.996811 (IQR 0.786486 to 1.000000)
- T2* log spatial correlation: 0.993745 (IQR 0.977680 to 0.999065)
- T2* voxel fraction with >5% absolute difference: 0.019666 (IQR 0.003542 to 0.050143)
- Optcom normalized RMSE: 0.030929 (IQR 0.014011 to 0.059554)
- Optcom median voxelwise temporal correlation: 1.000000 (IQR 1.000000 to 1.000000)

N=0 controls receive identical commands and serve as a numerical pipeline check. Run-level effects remain in `paired_t2s.tsv`; no arbitrary consequential-effect threshold is imposed here.

## FastICA Versus RobustICA

- Historical to NSS-aware FastICA ICA-count change: 1.0000 (IQR 0.0000 to 3.0000)
- Historical to NSS-aware FastICA rejected-fraction change: 0.0455 (IQR -0.0059 to 0.0968)
- Change in ICA count: -3.0000 (IQR -6.0000 to -1.0000)
- Change in rejected fraction: 0.0000 (IQR -0.0569 to 0.0304)
- Change in rejected variance: 0.0026 (IQR -0.0749 to 0.0266)
- RobustICA mean index quality: 0.9396 (IQR 0.9284 to 0.9484)
- Runs with index quality below 0.6: 0
- RobustICA FastICA convergence warnings: 30 total across 51 reported runs.

## Denoising QC

- RobustICA minus FastICA denoised tSNR: -1.4850 (IQR -5.5169 to -0.0155)
- RobustICA minus FastICA median DVARS: 6.2474 (IQR 0.3981 to 13.0241)
- FastICA/RobustICA voxelwise temporal correlation: 0.950369 (IQR 0.902313 to 0.978097)
- FastICA FD-versus-denoised-DVARS Spearman correlation: 0.2582 (IQR 0.0287 to 0.4032)
- RobustICA FD-versus-denoised-DVARS Spearman correlation: 0.2511 (IQR 0.1347 to 0.5307)

## Interpretation Gate

These paired summaries determine which effects need visual review and whether the optional Motion24 audit should proceed. They do not select a production winner, use task regressors, alter classifications, or justify a cohort-wide RobustICA rerun by themselves.

The next reviewed pass should inspect `review_manifest.tsv`, examine run-level outliers, and add Motion24 metrics only after confirming that these aggregate calculations are scientifically sensible.
