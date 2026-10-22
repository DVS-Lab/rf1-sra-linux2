# Katie and Sophia: Validated Imaging Handoff

**Current handoff, October 22, 2026.** Use this page for the papers' revised
**age-55+, ses-01 activation analyses without TEDANA nuisance regressors**.
Age was selected from Linux2's `bids/participants.tsv`.

## Starting Imaging Ns and Files

| Paper / task | Imaging starting N | Selected inputs on Linux2 |
| --- | ---: | --- |
| Katie / Social Doors | **137** | `/ZPOOL/data/projects/rf1-sra-linux2/work/coverage95-handoff-20261021-204525/socialdoors/selected_inputs.tsv` |
| Sophia / UGR | **145** | `/ZPOOL/data/projects/rf1-sra-linux2/work/coverage95-handoff-20261021-204525/ugr/selected_inputs.tsv` |

These are unique participants **after the imaging selection below**, not final
paper Ns. Every selected participant is age 55+. Each task directory also has
`subjects.txt`; rows in `selected_inputs.tsv` repeat across contrasts, so do not
use its total row count as participant N.

The handoff root contains `run_decisions.tsv` (selection reasons and QC values),
`counts.tsv`, and provenance files:

```text
/ZPOOL/data/projects/rf1-sra-linux2/work/coverage95-handoff-20261021-204525/
```

The separate Doors input table is `doors/selected_inputs.tsv` under that root
(imaging N = 136). It is not the Social Doors input or a combined-task mean.
The TSVs and imaging outputs remain on Linux2; this README is the canonical
human-readable handoff. A permission error is an access issue, not a participant
exclusion or a reason to substitute an older input list.

## Revised Imaging Rules

- Preserve all settled source-validity exclusions and explicit reviewed run holds.
- Require **coverage >=95% per run** of the fixed canonical QC reference mask.
  Exactly 95% passes; missing/invalid coverage is withheld. This replaces the old
  boxplot coverage criterion. The reference omits historical cerebellum/brainstem
  regions; it is not literally all brain tissue.
- **No TEDANA-component-count exclusion.** These outputs use base fMRIPrep
  nuisance regressors without TEDANA rejected-component regressors.
- Do not reapply old aggregate imaging-outlier exclusions. FD, tSNR, and other
  QC flags are descriptive unless an explicit reviewed exclusion applies.
- Evaluate each task/session independently. Ses-02 cannot exclude ses-01;
  Doors cannot exclude Social Doors. There is no blanket subject-level QC exclusion.
- Preserve good UGR runs. The table already selects paired L2 when both runs
  qualify, or single-run L1 when only one qualifies. Do not substitute a paired
  L2 containing an excluded run.

## Jacob's Next Steps

1. Intersect these imaging inputs with each paper's approved survey/linkage cohort
   **before its previous imaging-QC exclusions**, not the old final sample.
2. Filter the selected-input table to the intended contrast. Use its exact cope,
   varcope, mask, and DOF paths; there must be one input per participant/contrast.
3. Rebuild and validate the L3 input/design/covariate row order, then run L3.
   Do not reuse old L3 lists or regenerate paths from participant IDs.
4. Report the final unique-participant N and reasons for nonselection after the
   paper-specific intersection. **137 and 145 are starting pools, not final Ns.**

No L1/L2 rerun is needed for these validated selected inputs. The ongoing
cohort TEDANA variant benchmark does not block these no-TEDANA analyses.

## Validation Record

The [coverage95 handoff check](../../logs/records/20261021-204525_coverage95-handoff-20261021-204525.md)
verified 557 L1 and 271 L2 outputs, input lineage, eligible run subsets, settled
decisions, and one selected input per participant/contrast. Both exits were 0.
The [magnitude/phase audit](../../logs/records/20261022-005218_duplicate-task-series-roles-20261022-005218.md)
verified all 386 saved sessions and cleared 2,413 alternative-rule artifacts;
it did not change eligibility. Technical validation does not establish final
paper Ns or certify an L3 fit. See the [technical runbook](../coverage95-paper-handoff.md)
for regeneration details; do not overwrite this validated snapshot.
