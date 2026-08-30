# TEDANA Motion24 Sentinel Audit

This audit measures how strongly each existing ICA timecourse resembles the conventional 24-parameter rigid-body motion model. Motion metrics did not participate in classification, and production derivatives were not modified.

## Validation

- Sentinel runs: 51
- Component rows: 4736
- Motion24 classifications were required to match the corresponding ordinary NSS-aware run exactly.

## Continuous Distributions

- fastica accepted: Motion24 R-squared 0.3203 (IQR 0.2293 to 0.4725); 860/1247 components exceed the descriptive 0.25 threshold.
- fastica rejected: Motion24 R-squared 0.3459 (IQR 0.2080 to 0.5635); 907/1359 components exceed the descriptive 0.25 threshold.
- robustica accepted: Motion24 R-squared 0.3117 (IQR 0.2185 to 0.4956); 657/998 components exceed the descriptive 0.25 threshold.
- robustica rejected: Motion24 R-squared 0.3386 (IQR 0.2009 to 0.5587); 745/1132 components exceed the descriptive 0.25 threshold.

## Review Priorities

- Accepted components with Motion24 R-squared >0.25: 1517
- Rejected components with Motion24 R-squared <0.10: 124
- `review_manifest.tsv` selects the highest-motion accepted component, lowest-motion rejected component, and largest-variance rejected component for each run and ICA configuration. Duplicate selections are combined.

## Interpretation Gate

The 0.10, 0.25, and 0.50 values are descriptive summaries, not classification thresholds. Motion resemblance alone does not override TE dependence. Human component review is required before considering any motion-informed decision rule or production migration.
