# Katie and Sophia: Validated Imaging Handoff

## Current Status: Katie Diagnostic Pending

**October 27 update:** do not finalize Katie's FD/tSNR exclusions yet. The PI
requested a [paired-difference diagnostic](../socialdoors-paired-diagnostic.md)
including FD/tSNR-flagged pairs, while preserving settled source exclusions and
>=95% coverage for each run. The strict both-tasks-pass selection below is now a
comparison set, not a final instruction for Katie. No exclusion will be assigned
solely because the Social Doors minus Doors effect is extreme. Sophia's verified
UGR handoff is unchanged.

## Verified FD/tSNR Handoff and Strict Comparison

The October 27 FD/tSNR handoff passed build and check (both exit 0): independent
imaging Ns are UGR **137**, Social Doors **129**, and Doors **124**. These are not
paper Ns. See the [validation record](../../logs/records/20261027-141630_coverage95-fd-tsnr-handoff-20261027-141630.md).

The strict comparison requires **both tasks to pass** in the same session. That
table-only intersection is available using
[the paired handoff commands](../fd-tsnr-paper-handoff.md#paired-task-finalization),
but is not the final Katie selection while the paired diagnostic is pending.
UGR selections stay byte-for-byte unchanged; settled exclusions remain binding.
The paired N must come from this final validation, not from either independent N.

After its check passes, the strict comparison uses this Linux2 root:

```text
/ZPOOL/data/projects/rf1-sra-linux2/work/paper-handoff-fd-tsnr-paired-v1/
```

- Katie: `paired_socialdoors/selected_pairs.tsv` explicitly pairs the corresponding
  Social Doors and Doors L1 estimates, variance images, masks and DOF files.
- The `socialdoors/selected_inputs.tsv` and `doors/selected_inputs.tsv` tables
  contain the identical paired subjects in matching contrast order.
- Sophia: `ugr/selected_inputs.tsv`, retaining the verified paired L2 or single-run
  L1 choice based on passing UGR runs.
- `counts.tsv` and `paired_membership.tsv` document imaging Ns and pairing losses.

These are analysis inputs, not newly computed Social Doors minus Doors maps.
The existing cross-task L2 template has a single all-ones EV/contrast and computes
a mean; it must not substitute for the difference. Use the matched L1 estimates
in the downstream within-participant contrast procedure. Do not compare the tasks
as unpaired groups. Intersect with the unchanged October 26 survey/linkage cohorts,
then rebuild aligned L3 inputs once Katie's policy is finalized and report final paper Ns. Do not reapply aggregate
QC or TEDANA exclusions. No preprocessing, L1, or UGR L2 rerun is needed.

## Background to the Correction

**Correction, October 27, 2026: the coverage-only handoff below is superseded
for L3 selection.** It did not enforce the intended mean-FD and tSNR exclusions.
Use the [replacement build and validation instructions](../fd-tsnr-paper-handoff.md).
The replacement uses upper-tail FD and lower-tail tSNR 1.5-IQR fences within
task/session, alongside coverage >=95%, and preserves settled exclusions.
No TEDANA-count exclusion applies. It selects a passing single-run UGR L1 when
the old paired L2 includes a newly excluded run. Do not merely filter subjects
from the old input table. New Linux2 validation must establish the corrected Ns
and paths; 137/145 and the subsequent 110/116 are not final corrected-policy Ns.

## Historical Coverage-Only Handoff

The information below records the October 22 handoff, not current instructions.
It describes the papers' revised
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
- Historical policy only: FD and tSNR flags were descriptive. This is the error
  corrected by the October 27 replacement above. Never use the aggregate flag,
  which also contains TEDANA and the superseded boxplot coverage criterion.
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
