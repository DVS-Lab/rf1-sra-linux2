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
| XA60 | 1085 | 155 | 155 |

## Task doors, Session 01

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 30 [21.9, 34.8] | 31 [27.1, 35.9] | 42.2 [36.8, 48.5] |
| Mean framewise displacement | 0.159 [0.116, 0.243] | 0.176 [0.112, 0.304] | 0.15 [0.12, 0.206] |
| TEDANA rejected components | 9 [8, 12] | 12 [10, 14] | 22 [16, 32] |
| Brain coverage (%) | 99.9 [99.8, 99.9] | 99.9 [99.8, 100] | 99.5 [99.4, 99.7] |

## Task doors, Session 02

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | NA | 36.7 [36.7, 36.7] | 40.3 [34.9, 47.5] |
| Mean framewise displacement | NA | 0.123 [0.123, 0.123] | 0.192 [0.162, 0.221] |
| TEDANA rejected components | NA | 8 [8, 8] | 21 [15.5, 37.5] |
| Brain coverage (%) | NA | 99.7 [99.7, 99.7] | 99.5 [99.3, 99.7] |

## Task sharedreward, Session 01

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 27.5 [20.6, 33.2] | 30.1 [24.4, 33.4] | 41.3 [34.2, 47.4] |
| Mean framewise displacement | 0.167 [0.118, 0.257] | 0.18 [0.131, 0.279] | 0.162 [0.12, 0.208] |
| TEDANA rejected components | 10 [8, 13] | 11 [10, 13] | 26 [18, 39] |
| Brain coverage (%) | 99.9 [99.8, 99.9] | 99.9 [99.8, 100] | 99.5 [99.4, 99.7] |

## Task socialdoors, Session 01

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 28.7 [22.2, 34.8] | 29 [27.9, 34.6] | 43.6 [37.3, 50.5] |
| Mean framewise displacement | 0.16 [0.116, 0.235] | 0.198 [0.124, 0.239] | 0.151 [0.119, 0.2] |
| TEDANA rejected components | 10 [7, 12] | 12 [11, 15] | 22 [16, 33] |
| Brain coverage (%) | 99.9 [99.8, 99.9] | 99.9 [99.8, 100] | 99.6 [99.3, 99.7] |

## Task socialdoors, Session 02

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | NA | 36.6 [36.6, 36.6] | 39.2 [33.3, 47.9] |
| Mean framewise displacement | NA | 0.122 [0.122, 0.122] | 0.186 [0.16, 0.232] |
| TEDANA rejected components | NA | 10 [10, 10] | 22 [15, 34.5] |
| Brain coverage (%) | NA | 99.7 [99.7, 99.7] | 99.6 [99.4, 99.8] |

## Task trust, Session 01

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 27.4 [19.8, 33.5] | 31 [25.8, 36.5] | 41.1 [32.4, 47.8] |
| Mean framewise displacement | 0.17 [0.122, 0.253] | 0.149 [0.128, 0.211] | 0.161 [0.125, 0.222] |
| TEDANA rejected components | 10 [8, 13] | 13 [10.2, 15] | 25 [18, 42] |
| Brain coverage (%) | 99.9 [99.8, 99.9] | 99.9 [99.8, 100] | 99.5 [99.3, 99.7] |

## Task ugr, Session 01

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | 28.7 [22.2, 34] | 30.6 [26.8, 33.6] | 41.6 [34.6, 48.2] |
| Mean framewise displacement | 0.174 [0.119, 0.254] | 0.174 [0.129, 0.29] | 0.154 [0.121, 0.207] |
| TEDANA rejected components | 10 [8, 12] | 12.5 [10, 14.8] | 23 [16, 37] |
| Brain coverage (%) | 99.9 [99.8, 99.9] | 99.9 [99.8, 100] | 99.6 [99.4, 99.7] |

## Task ugr, Session 02

Values are median [Q1, Q3].

| Metric | E11 | XA30 | XA60 |
| --- | ---: | ---: | ---: |
| tSNR | NA | 37.7 [36.8, 38.7] | 40.7 [32.9, 44.8] |
| Mean framewise displacement | NA | 0.121 [0.119, 0.123] | 0.188 [0.163, 0.241] |
| TEDANA rejected components | NA | 11.5 [11.2, 11.8] | 24 [15, 34] |
| Brain coverage (%) | NA | 99.7 [99.7, 99.7] | 99.6 [99.5, 99.7] |

## Interpretation

Use `summary.tsv` for exact sample sizes, distributions, task/session-fence
flag rates, and median differences from E11. Large differences should be
followed by task/session-stratified and, where possible, within-subject
review before attributing them to scanner software. For brain coverage,
inspect raw acquisition coverage and fMRIPrep registration/masks to
distinguish acquisition from processing failures.
