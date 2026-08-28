# TEDANA Scanner-Era Forensic Audit

This audit separates nominal acquisition metadata from reconstructed-image properties. Cross-era results are observational and do not establish that scanner software caused a difference.

## Coverage

- Run properties complete: 2737/2737
- Within-subject cross-era pairs: 86
- Representative DICOM mappings: 24/24

## Sidecar Parameters

- differs_systematically_by_era: 192
- identical_across_eras: 1508
- insufficient_cross_era_coverage: 96
- varies_within_era: 508

## Interpretation Gate

A parameter absent from BIDS is not assumed invariant. Review `dicom_representatives.tsv` before interpreting raw-header results. If nominal sequence fields remain matched while XA60 differs in temporal, spectral, echo-wise, or PCA-spectrum properties, describe this as an association with reconstructed-data/noise properties rather than a proven causal XA60 effect.
