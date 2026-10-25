# RF1-SRA Imaging QC By Scanner Era

This report stratifies the canonical run-level QC metrics by the scanner
software era recorded in each BIDS echo-2 magnitude sidecar. It does not
recalculate thresholds within era and does not authorize exclusions.
Scanner era is associated with acquisition date and cohort composition, so
between-era differences are descriptive and should not be read as causal.
Coverage remains in the underlying table and policy; only its plot panel is replaced.
Smoothness is MRIQC's functional FWHM estimate, not the FEAT smoothing kernel
or smoothness measured on the final fMRIPrep/L1 outputs. No smoothness exclusion is applied.
MRIQC reports FWHM in voxels. Each axis is multiplied by its own MRIQC spacing
in mm; the plotted value is the arithmetic mean of those three mm estimates.
Source: https://github.com/nipreps/mriqc/blob/24.0.2/mriqc/interfaces/functional.py

## Inventory

| Era | Runs | Participants | Participant-sessions |
| --- | ---: | ---: | ---: |
| E11 | 1556 | 211 | 211 |
| XA30 | 140 | 18 | 18 |
| XA60 | 1090 | 156 | 156 |

## Task doors, Session 01

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 30 [21.9, 34.8] | 31 [27.1, 35.9] | 42.2 [36.9, 48.8] |
| Mean framewise displacement | 0.159 [0.116, 0.243] | 0.176 [0.112, 0.304] | 0.15 [0.121, 0.206] |
| TEDANA rejected components | 9 [8, 12] | 12 [10, 14] | 21.5 [16, 32] |
| MRIQC smoothness: mean FWHM (mm) | 6.95 [6.68, 7.25] | 8.16 [7.79, 8.43] | 10.5 [10.2, 10.7] |

XA60 minus XA30 median FWHM: 2.3 mm (28.2%).

| Era | FWHM runs / total | Participants with FWHM | Missing FWHM |
| --- | ---: | ---: | ---: |
| E11 | 197 / 197 | 197 | 0 |
| XA30 | 17 / 17 | 17 | 0 |
| XA60 | 124 / 124 | 124 | 0 |

## Task doors, Session 02

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | NA | 36.7 [36.7, 36.7] | 40.2 [33.5, 47.4] |
| Mean framewise displacement | NA | 0.123 [0.123, 0.123] | 0.191 [0.164, 0.22] |
| TEDANA rejected components | NA | 8 [8, 8] | 20.5 [14.5, 36.8] |
| MRIQC smoothness: mean FWHM (mm) | NA | 7.48 [7.48, 7.48] | 10.2 [9.71, 10.6] |

XA60 minus XA30 median FWHM: 2.76 mm (36.9%).

| Era | FWHM runs / total | Participants with FWHM | Missing FWHM |
| --- | ---: | ---: | ---: |
| XA30 | 1 / 1 | 1 | 0 |
| XA60 | 32 / 32 | 32 | 0 |

## Task sharedreward, Session 01

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 27.5 [20.6, 33.2] | 30.1 [24.4, 33.4] | 41.3 [34.2, 47.4] |
| Mean framewise displacement | 0.167 [0.118, 0.257] | 0.18 [0.131, 0.279] | 0.162 [0.12, 0.208] |
| TEDANA rejected components | 10 [8, 13] | 11 [10, 13] | 26 [18, 39] |
| MRIQC smoothness: mean FWHM (mm) | 6.98 [6.69, 7.31] | 8.16 [7.87, 8.47] | 10.5 [10.2, 10.8] |

XA60 minus XA30 median FWHM: 2.35 mm (28.7%).

| Era | FWHM runs / total | Participants with FWHM | Missing FWHM |
| --- | ---: | ---: | ---: |
| E11 | 395 / 395 | 208 | 0 |
| XA30 | 34 / 34 | 17 | 0 |
| XA60 | 239 / 239 | 123 | 0 |

## Task socialdoors, Session 01

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 28.7 [22.2, 34.8] | 29 [27.9, 34.6] | 43.6 [37.3, 50.5] |
| Mean framewise displacement | 0.16 [0.116, 0.235] | 0.198 [0.124, 0.239] | 0.151 [0.119, 0.2] |
| TEDANA rejected components | 10 [7, 12] | 12 [11, 15] | 22 [16, 33] |
| MRIQC smoothness: mean FWHM (mm) | 6.95 [6.68, 7.27] | 8.14 [7.81, 8.37] | 10.5 [10.1, 10.8] |

XA60 minus XA30 median FWHM: 2.33 mm (28.6%).

| Era | FWHM runs / total | Participants with FWHM | Missing FWHM |
| --- | ---: | ---: | ---: |
| E11 | 196 / 196 | 196 | 0 |
| XA30 | 17 / 17 | 17 | 0 |
| XA60 | 124 / 124 | 124 | 0 |

## Task socialdoors, Session 02

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | NA | 36.6 [36.6, 36.6] | 39.1 [32, 47.9] |
| Mean framewise displacement | NA | 0.122 [0.122, 0.122] | 0.187 [0.16, 0.231] |
| TEDANA rejected components | NA | 10 [10, 10] | 21 [14, 33.8] |
| MRIQC smoothness: mean FWHM (mm) | NA | 7.53 [7.53, 7.53] | 10.3 [9.73, 10.6] |

XA60 minus XA30 median FWHM: 2.74 mm (36.4%).

| Era | FWHM runs / total | Participants with FWHM | Missing FWHM |
| --- | ---: | ---: | ---: |
| XA30 | 1 / 1 | 1 | 0 |
| XA60 | 32 / 32 | 32 | 0 |

## Task trust, Session 01

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 27.4 [19.8, 33.5] | 31 [25.8, 36.5] | 41.1 [32.4, 47.8] |
| Mean framewise displacement | 0.17 [0.122, 0.253] | 0.149 [0.128, 0.211] | 0.161 [0.125, 0.222] |
| TEDANA rejected components | 10 [8, 13] | 13 [10.2, 15] | 25 [18, 42] |
| MRIQC smoothness: mean FWHM (mm) | 6.98 [6.69, 7.33] | 8.11 [7.88, 8.56] | 10.5 [10.2, 10.9] |

XA60 minus XA30 median FWHM: 2.42 mm (29.8%).

| Era | FWHM runs / total | Participants with FWHM | Missing FWHM |
| --- | ---: | ---: | ---: |
| E11 | 380 / 380 | 204 | 0 |
| XA30 | 34 / 34 | 17 | 0 |
| XA60 | 238 / 238 | 123 | 0 |

## Task ugr, Session 01

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 28.7 [22.2, 34] | 30.6 [26.8, 33.6] | 41.6 [34.6, 48.2] |
| Mean framewise displacement | 0.174 [0.119, 0.254] | 0.174 [0.129, 0.29] | 0.154 [0.121, 0.207] |
| TEDANA rejected components | 10 [8, 12] | 12.5 [10, 14.8] | 23 [16, 37] |
| MRIQC smoothness: mean FWHM (mm) | 6.96 [6.69, 7.29] | 8.16 [7.88, 8.35] | 10.5 [10.2, 10.8] |

XA60 minus XA30 median FWHM: 2.34 mm (28.6%).

| Era | FWHM runs / total | Participants with FWHM | Missing FWHM |
| --- | ---: | ---: | ---: |
| E11 | 388 / 388 | 205 | 0 |
| XA30 | 34 / 34 | 17 | 0 |
| XA60 | 238 / 238 | 121 | 0 |

## Task ugr, Session 02

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | NA | 37.7 [36.8, 38.7] | 40.6 [32.3, 44.7] |
| Mean framewise displacement | NA | 0.121 [0.119, 0.123] | 0.188 [0.164, 0.244] |
| TEDANA rejected components | NA | 11.5 [11.2, 11.8] | 23 [14.5, 34] |
| MRIQC smoothness: mean FWHM (mm) | NA | 7.47 [7.47, 7.48] | 10.3 [9.72, 10.8] |

XA60 minus XA30 median FWHM: 2.83 mm (37.9%).

| Era | FWHM runs / total | Participants with FWHM | Missing FWHM |
| --- | ---: | ---: | ---: |
| XA30 | 2 / 2 | 1 | 0 |
| XA60 | 63 / 63 | 32 | 0 |

## Interpretation

Use `summary.tsv` for exact sample sizes, distributions, task/session-fence
flag rates, axis-specific FWHM, missingness, and median differences from E11 and XA30.
All measurements are retained regardless of QC flags. Repeated runs are not
independent participants; these are run-level descriptive comparisons, not significance tests.
Inspect voxel spacing and MRIQC versions in run_metrics.tsv before interpreting differences.
Large differences should be
followed by task/session-stratified and, where possible, within-subject
review before attributing them to scanner software or sequence changes.
