# RF1-SRA TEDANA Audit

This report describes the historical production baseline. It does not change component classifications or production derivatives.

## Cohort Inventory

- Acquired runs inventoried: 2749
- Complete audit rows: 2749
- Incomplete audit rows: 0
- Sentinel runs selected: 51
- NSS distribution: N=0: 402, N=1: 1251, N=2: 816, N=3: 196, N=4: 57, N=5: 14, N=6: 7, N=7: 5, N=8: 1

## Descriptive Associations

Spearman correlations are descriptive and are not used for classification.

| Outcome | Predictor | N | Spearman rho |
| --- | --- | ---: | ---: |
| `n_rejected` | `n_ica` | 2749 | 0.7613 |
| `n_rejected` | `mean_fd` | 2749 | 0.2226 |
| `n_rejected` | `p95_fd` | 2749 | 0.2339 |
| `n_rejected` | `max_fd` | 2749 | 0.1722 |
| `n_rejected` | `fraction_fd_gt_0_2` | 2749 | 0.2002 |
| `n_rejected` | `fraction_fd_gt_0_5` | 2749 | 0.1754 |
| `n_rejected` | `p95_standardized_dvars` | 2749 | 0.6804 |
| `n_rejected` | `nss_count` | 2749 | -0.2345 |
| `rejected_fraction` | `n_ica` | 2749 | 0.1708 |
| `rejected_fraction` | `mean_fd` | 2749 | -0.0695 |
| `rejected_fraction` | `p95_fd` | 2749 | -0.0935 |
| `rejected_fraction` | `max_fd` | 2749 | -0.1752 |
| `rejected_fraction` | `fraction_fd_gt_0_2` | 2749 | -0.0621 |
| `rejected_fraction` | `fraction_fd_gt_0_5` | 2749 | -0.1597 |
| `rejected_fraction` | `p95_standardized_dvars` | 2749 | 0.3370 |
| `rejected_fraction` | `nss_count` | 2749 | -0.2390 |
| `rejected_normalized_variance` | `n_ica` | 2749 | 0.0369 |
| `rejected_normalized_variance` | `mean_fd` | 2749 | -0.0857 |
| `rejected_normalized_variance` | `p95_fd` | 2749 | -0.0946 |
| `rejected_normalized_variance` | `max_fd` | 2749 | -0.1125 |
| `rejected_normalized_variance` | `fraction_fd_gt_0_2` | 2749 | -0.0973 |
| `rejected_normalized_variance` | `fraction_fd_gt_0_5` | 2749 | -0.1100 |
| `rejected_normalized_variance` | `p95_standardized_dvars` | 2749 | 0.0015 |
| `rejected_normalized_variance` | `nss_count` | 2749 | -0.1405 |

## Motion24 Component Fits

- Accepted: N=49576, median R2=0.3731; R2>0.10: 48517, R2>0.25: 35297, R2>0.50: 17045
- Rejected: N=49573, median R2=0.3636; R2>0.10: 47111, R2>0.25: 33858, R2>0.50: 16831

## Benchmark Status

The sentinel manifest is ready for controlled T2S-FULL, T2S-EXCLUDE-NSS, NSS-aware FastICA, and NSS-aware RobustICA runs. No benchmark result is interpreted until those isolated derivatives have completed and passed validation.

## Production Decision

No production change is authorized by this baseline audit. The benchmark must determine whether NSS handling or RobustICA materially improves the data before `tedana.sh`, confound construction, or QC thresholds are revised.
