# Events Response QC

This directory holds the policy and canonical outputs for the dedicated
response-miss audit of BIDS events. The audit is read-only with respect to BIDS
and imaging derivatives.

The historical Social Doors/Doors rule marks a run with at least 25% missed
decisions for review. The audit reports that threshold for every supported task
but does not turn it into an automatic cross-task exclusion. It separately
identifies sustained terminal miss blocks that may reflect a button-box failure.
A salvage candidate is a prompt for independent review, not permission to trim
or analyze the run.

Canonical generated outputs under `results/` are:

- `run_response_qc.tsv`: every audited events run and its full response metrics.
- `review_candidates.tsv`: runs crossing a trial-count, overall-miss, or
  terminal-streak review rule.
- `miss_fraction_by_task.png`: cohort-wide run miss fractions.
- `review_miss_patterns.png`: ordered response/miss sequences for review runs.
- `provenance.json`: hashes of the policy, subject list, and events inventory.

Important columns include the first and longest miss runs, the terminal miss
streak, its first trial and onset, the miss fraction before that block, and the
fraction of trials preceding it. `terminal_miss_start_onset_sec` describes the
events timeline only. It is not yet an approved fMRI truncation boundary.

Run on Linux2 with the production subject list:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2/code

QC_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
PRODUCTION_LIST=../logs/runlists/full-confounds-20260821-203754_production.txt

"$QC_PYTHON" build_events_qc.py build \
  --sublist "$PRODUCTION_LIST" \
  --dry-run

"$QC_PYTHON" build_events_qc.py build \
  --sublist "$PRODUCTION_LIST" \
  --overwrite

"$QC_PYTHON" build_events_qc.py check \
  --sublist "$PRODUCTION_LIST"
```

Review the generated TSV and PNG files before defining any image-trimming
workflow. A future repair must preserve original fMRIPrep/TEDANA products and
record a reviewed temporal cutoff separately from this descriptive audit.
