# Katie and Sophia: Validated Imaging Handoff

## Current Handoff: Validated Randomise Inputs

**October 29: build and independent check both passed (exit 0).** The
[validation record](../../logs/records/20261029-142504_socialdoors-randomise-pool-20261029-142504.md)
confirms **121 participants**, four signed Social Doors minus Doors COPE stacks,
finite masked pixels, matching subject/QC row order, and original input lineage.
Each contrast's common mask contains 80,305 voxels. This is the age-55+, ses-01
**imaging pool, not yet Katie's final paper cohort**. No randomise analysis has
been run. Existing processing and settled exclusions are unchanged.

### Validated Paths on Linux2

All files below are relative to this existing bundle root:

```text
/ZPOOL/data/projects/rf1-sra-linux2/work/randomise-socialdoors-age55-pool-v1/
```

| File | Meaning |
| --- | --- |
| `cope-1/difference_4d.nii.gz` | Social Doors win minus Doors win |
| `cope-2/difference_4d.nii.gz` | Social Doors loss minus Doors loss |
| `cope-3/difference_4d.nii.gz` | Social Doors decision minus Doors decision |
| `cope-4/difference_4d.nii.gz` | (Social Doors win-loss) minus (Doors win-loss) |
| `cope-1/mask.nii.gz` through `cope-4/mask.nii.gz` | Corresponding common analysis masks |
| `subjects.tsv` | Exact volume order, with zero-based index and one-based volume number |
| `cohort_ids.tsv` | Same ordered participant IDs in a single `subject` column |
| `qc_covariates_raw.tsv` | Constituent run metrics, signed FD/tSNR differences, and pair means |
| `qc_covariates_centered.tsv` | Candidate QC covariates demeaned over these 121 participants |
| `covariate_centering.json` | Centering means, units, constant columns and candidate rank |

The images are **effect differences, not t/Z differences or cross-task means**.
They use the existing **sm5 no-TEDANA L1 estimates**, not the experimental AFNI
6-mm outputs. Use the mask for the chosen contrast and preserve subject order.

### Exclusions Versus Model Covariates

Imaging selection is already applied: settled source exclusions, coverage
**>=95%**, upper-tail FD and lower-tail tSNR **1.5-IQR fences within task/session**,
with **both constituent runs required to pass**. Do not reapply older pooled-task,
coverage-only, or TEDANA-count exclusions. No paired-effect-outlier exclusion is
used. The broader 135-pair diagnostic below is not this selected 121-pair bundle.

QC covariates are separate candidate model adjustments, not further exclusions:
`delta_fd` and `delta_tsnr` are Social Doors minus Doors; `pair_mean_fd` and
`pair_mean_tsnr` describe overall pair quality. No model automatically includes
all four. The current centered values apply to all 121 participants; **do not use
them unchanged after subsetting**.

### Jacob's Next Step: Final Cohort List

Please commit an **ordered, one-column TSV headed `subject`**, containing unique
RF1 IDs after the approved survey/linkage requirements and intersection with
this strict 121-pair imaging pool, to this repository at:

```text
docs/paper-handoff/cohorts/katie-final.tsv
```

The corresponding Linux2 path will be
`/ZPOOL/data/projects/rf1-sra-linux2/docs/paper-handoff/cohorts/katie-final.tsv`.
**This file is still needed; it has not been supplied or generated.** No names,
DOB, raw survey records, or new exclusion review are required. Supply a separate
roster if a different model uses a different sample.

Once the roster is synchronized through Git, we will assemble the exact final
subset, recompute its common masks, recenter its QC covariates, validate alignment,
and report its final N. No preprocessing or L1 rerun is needed. The resulting
`work/randomise-katie-final-v1/` bundle is **not yet built or validated**. See the
[exact build/check and log-publishing commands](../socialdoors-randomise-bundle.md).

If we are also assembling the randomise design, send the participant-keyed
predictor/covariate table and existing model specification: coding, planned
contrasts, chosen QC terms, and any exchangeability restrictions. The image
bundle does not guess `design.mat`/`design.con` or launch an analysis.

**Sophia/UGR is unchanged:** 137 imaging participants, preserving good single
runs, at
`/ZPOOL/data/projects/rf1-sra-linux2/work/coverage95-fd-tsnr-handoff-20261027-141630/ugr/selected_inputs.tsv`.
That imaging count is also distinct from the final survey/linkage paper N.

## Background: Paired Diagnostic Reviewed

**October 27 review:** the [paired diagnostic passed](../../logs/records/20261027-145845_socialdoors-paired-diagnostic-20261027-145845.md)
with 135 source-valid, coverage-passing pairs: **121 pass both tasks' FD/tSNR
rules; 14 have high FD; none has low-tSNR failure**. The flagged pairs still have
higher uncertainty after subtraction. The recommendation is to retain the
already-specified FD/tSNR rules for the primary analysis, not replace them with
exclusions based on observed effects. The broader 135-pair set is available for
a labeled sensitivity analysis. See the [review and plots](../../qc/paired_difference/socialdoors-v1/README.md).

The explicit **121-pair input list is now in Git**:

```text
/ZPOOL/data/projects/rf1-sra-linux2/qc/paired_difference/socialdoors-v1/strict_pairs.tsv
```

It has four corresponding contrasts per participant and both tasks' exact L1
COPE/VARCOPE/mask/DOF paths. No further pairing job is needed. Filter to the
intended contrast and intersect with Katie's approved survey/linkage roster
before its old imaging-QC exclusions. **121 is the imaging N, not the final paper
N.** No new exclusion based on contrast effects or uncertainty is assigned.

Sophia's verified UGR selection is unchanged: **137 imaging participants**, using
`/ZPOOL/data/projects/rf1-sra-linux2/work/coverage95-fd-tsnr-handoff-20261027-141630/ugr/selected_inputs.tsv`.
Good single-run UGR inputs remain preserved. Settled source exclusions, >=95%
coverage and the absence of a TEDANA-component-count exclusion remain unchanged.

## Verified FD/tSNR Handoff and Strict Comparison

The October 27 FD/tSNR handoff passed build and check (both exit 0): independent
imaging Ns are UGR **137**, Social Doors **129**, and Doors **124**. These are not
paper Ns. See the [validation record](../../logs/records/20261027-141630_coverage95-fd-tsnr-handoff-20261027-141630.md).

The strict intersection requires **both tasks to pass** in the same session.
Its 121-pair membership is verified by the diagnostic and independently reproduced
from the numeric QC values in the Git-shared table above. UGR selections stay
byte-for-byte unchanged; settled exclusions remain binding.

The older table-only paired wrapper, if run, writes to the root below. It is
not needed to use the Git-shared 121-pair list above; do not assume it exists:

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

Those older table-only outputs are analysis inputs, not newly computed Social
Doors minus Doors maps. The validated difference stacks are now available at the
bundle path at the top of this README.
The existing cross-task L2 template has a single all-ones EV/contrast and computes
a mean; it must not substitute for the difference. Use the matched L1 estimates
in the downstream within-participant contrast procedure. Do not compare the tasks
as unpaired groups. Intersect with the unchanged October 26 survey/linkage cohorts,
then rebuild aligned L3 inputs under the agreed policy and report final paper Ns. Do not reapply aggregate
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
