# RF1-SRA Imaging QC By Scanner Era

This report stratifies the canonical run-level QC metrics by the scanner
software era recorded in each BIDS echo-2 magnitude sidecar. It does not
recalculate thresholds within era and does not authorize exclusions.
Scanner era is associated with acquisition date and cohort composition, so
between-era differences are descriptive and should not be read as causal.

## Inventory

| Era | Runs | Participants | Participant-sessions |
| --- | ---: | ---: | ---: |
| E11 | 1556 | 211 | 211 |
| XA30 | 140 | 18 | 18 |
| XA60 | 1065 | 150 | 150 |

## Sharedreward

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 27.5 [20.6, 33.3] | 30.1 [24.4, 33.4] | 41.3 [34.2, 47.4] |
| Mean framewise displacement | 0.167 [0.118, 0.257] | 0.18 [0.131, 0.279] | 0.162 [0.12, 0.208] |
| TEDANA rejected components | 10 [8, 13] | 11 [10, 13] | 26 [18, 39] |
| Brain coverage (%) | 99.9 [99.8, 99.9] | 99.9 [99.8, 100] | 99.5 [99.4, 99.7] |

## Trust

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 27.5 [19.8, 33.5] | 31 [25.8, 36.5] | 41.1 [32.4, 47.8] |
| Mean framewise displacement | 0.17 [0.121, 0.253] | 0.149 [0.128, 0.211] | 0.161 [0.125, 0.222] |
| TEDANA rejected components | 10 [8, 13] | 13 [10.2, 15] | 25 [18, 42] |
| Brain coverage (%) | 99.9 [99.8, 99.9] | 99.9 [99.8, 100] | 99.5 [99.3, 99.7] |

## Ugr

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 28.7 [22.2, 34] | 31.5 [27.5, 34.1] | 41.5 [34.5, 47.9] |
| Mean framewise displacement | 0.174 [0.119, 0.254] | 0.172 [0.123, 0.285] | 0.166 [0.129, 0.221] |
| TEDANA rejected components | 10 [8, 12] | 12 [10, 14.2] | 24 [17, 37] |
| Brain coverage (%) | 99.9 [99.8, 99.9] | 99.9 [99.8, 100] | 99.6 [99.4, 99.7] |

## Socialdoors

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 29.5 [22.1, 34.8] | 30.9 [27.9, 36] | 42.6 [36.7, 49.2] |
| Mean framewise displacement | 0.16 [0.116, 0.238] | 0.176 [0.119, 0.244] | 0.16 [0.125, 0.216] |
| TEDANA rejected components | 10 [8, 12] | 12 [10, 14.2] | 22 [16.5, 33] |
| Brain coverage (%) | 99.9 [99.8, 99.9] | 99.9 [99.8, 100] | 99.5 [99.3, 99.7] |

## Interpretation

Use `summary.tsv` for exact sample sizes, distributions, pooled-fence
flag rates, and median differences from E11. Large differences should be
followed by task/session-stratified and, where possible, within-subject
review before attributing them to scanner software. For brain coverage,
inspect raw acquisition coverage and fMRIPrep registration/masks to
distinguish acquisition from processing failures.
