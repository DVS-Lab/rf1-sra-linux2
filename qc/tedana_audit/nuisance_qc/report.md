# TEDANA Nuisance-Model QC

This audit compares nuisance spaces fitted to the same full-length canonical fMRIPrep BOLD. It does not residualize, replace, or create a production BOLD input. RF1 continues to fit task and nuisance EVs simultaneously in FEAT.

## Coverage

- Sentinel runs: 51
- Condition/run rows: 153
- Pair rows: 102
- N=0 FULL/NSS numerical identity checks: 11

## Conditions

- BASE: selected fMRIPrep confounds.
- TEDANA-FULL: BASE plus rejected ICs from the matched full-volume decomposition.
- TEDANA-NSS: BASE plus rejected ICs from the NSS-aware decomposition, with exactly N leading zero rows.

Metrics are evaluated on N:T. Nuisance columns are mean-centered before projection so the adjusted series retains its temporal mean. An increase in residual tSNR is mechanically favored whenever added regressors reduce residual variance, including irrelevant regressors, so it is a weak descriptive metric rather than evidence of effective artifact removal. A standardized-DVARS value above 1.5 is a descriptive high-DVARS frame, not an exclusion rule.

## Interpretation Gate

Use BASE-vs-FULL to estimate artifact-control benefit and FULL-vs-NSS to isolate NSS handling. Prioritize motion-linked residual structure, DVARS, incremental rank, residual degrees of freedom, and actual task/contrast efficiency over tSNR. No single QC metric authorizes a production change.
