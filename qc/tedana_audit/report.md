# RF1-SRA TEDANA Audit

This report describes the historical production baseline. It does not change component classifications or production derivatives.

## Cohort Inventory

- Acquired runs inventoried: 2741
- Complete audit rows: 2737
- Incomplete audit rows: 4
- Sentinel runs selected: 51
- NSS distribution: N=0: 402, N=1: 1243, N=2: 813, N=3: 196, N=4: 56, N=5: 14, N=6: 7, N=7: 5, N=8: 1

## Descriptive Associations

Spearman correlations are descriptive and are not used for classification.

| Outcome | Predictor | N | Spearman rho |
| --- | --- | ---: | ---: |
| `n_rejected` | `n_ica` | 2737 | 0.7616 |
| `n_rejected` | `mean_fd` | 2737 | 0.2226 |
| `n_rejected` | `p95_fd` | 2737 | 0.2345 |
| `n_rejected` | `max_fd` | 2737 | 0.1736 |
| `n_rejected` | `fraction_fd_gt_0_2` | 2737 | 0.1994 |
| `n_rejected` | `fraction_fd_gt_0_5` | 2737 | 0.1767 |
| `n_rejected` | `p95_standardized_dvars` | 2737 | 0.6811 |
| `n_rejected` | `nss_count` | 2737 | -0.2355 |
| `rejected_fraction` | `n_ica` | 2737 | 0.1713 |
| `rejected_fraction` | `mean_fd` | 2737 | -0.0704 |
| `rejected_fraction` | `p95_fd` | 2737 | -0.0938 |
| `rejected_fraction` | `max_fd` | 2737 | -0.1753 |
| `rejected_fraction` | `fraction_fd_gt_0_2` | 2737 | -0.0634 |
| `rejected_fraction` | `fraction_fd_gt_0_5` | 2737 | -0.1594 |
| `rejected_fraction` | `p95_standardized_dvars` | 2737 | 0.3359 |
| `rejected_fraction` | `nss_count` | 2737 | -0.2397 |
| `rejected_normalized_variance` | `n_ica` | 2737 | 0.0392 |
| `rejected_normalized_variance` | `mean_fd` | 2737 | -0.0857 |
| `rejected_normalized_variance` | `p95_fd` | 2737 | -0.0940 |
| `rejected_normalized_variance` | `max_fd` | 2737 | -0.1118 |
| `rejected_normalized_variance` | `fraction_fd_gt_0_2` | 2737 | -0.0974 |
| `rejected_normalized_variance` | `fraction_fd_gt_0_5` | 2737 | -0.1086 |
| `rejected_normalized_variance` | `p95_standardized_dvars` | 2737 | 0.0014 |
| `rejected_normalized_variance` | `nss_count` | 2737 | -0.1410 |

## Motion24 Component Fits

- Accepted: N=49401, median R2=0.3731; R2>0.10: 48344, R2>0.25: 35165, R2>0.50: 16988
- Rejected: N=49318, median R2=0.3635; R2>0.10: 46858, R2>0.25: 33672, R2>0.50: 16744

## Benchmark Status

The sentinel manifest is ready for controlled T2S-FULL, T2S-EXCLUDE-NSS, NSS-aware FastICA, and NSS-aware RobustICA runs. No benchmark result is interpreted until those isolated derivatives have completed and passed validation.

## Production Decision

No production change is authorized by this baseline audit. The benchmark must determine whether NSS handling or RobustICA materially improves the data before `tedana.sh`, confound construction, or QC thresholds are revised.

## Incomplete Runs

- `sub-11078_ses-02_task-doors_run-1`: missing_echo_1;missing_echo_2;missing_echo_3;missing_echo_4;missing_confounds;missing_fmriprep_mask;missing_tedana_metrics;missing_tedana_mixing
- `sub-11078_ses-02_task-socialdoors_run-1`: missing_echo_1;missing_echo_2;missing_echo_3;missing_echo_4;missing_confounds;missing_fmriprep_mask;missing_tedana_metrics;missing_tedana_mixing
- `sub-11078_ses-02_task-ugr_run-1`: missing_echo_1;missing_echo_2;missing_echo_3;missing_echo_4;missing_confounds;missing_fmriprep_mask;missing_tedana_metrics;missing_tedana_mixing
- `sub-11078_ses-02_task-ugr_run-2`: missing_echo_1;missing_echo_2;missing_echo_3;missing_echo_4;missing_confounds;missing_fmriprep_mask;missing_tedana_metrics;missing_tedana_mixing
