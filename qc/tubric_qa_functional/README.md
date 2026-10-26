# RF1 Functional-Only TUBRIC QA

**Current functional report, generated 2026-10-26 from the verified saved
[all-modality snapshot](../tubric_qa/).** This is a scoped view of existing
measurements, not a new live BIDS inventory. No MRIQC or other processing ran.
The original report, completed images and settled exclusions remain unchanged.

## Plots And Dashboard

Each plot shows smoothness in mm, tSNR and mean FD. These echo-2 plots match
the representative echo used by our canonical QC:

| Task | Session 01 | Session 02 |
| --- | --- | --- |
| Doors | [Plot](figures/group-e64943e063a7-page-1.png) | [Plot](figures/group-10f4514f26cc-page-1.png) |
| Social Doors | [Plot](figures/group-9e706811be66-page-1.png) | [Plot](figures/group-7b594d8993a9-page-1.png) |
| UGR | [Plot](figures/group-d6ab7b4b5352-page-1.png) | [Plot](figures/group-1953a7a48679-page-1.png) |
| Shared Reward | [Plot](figures/group-e92b47495998-page-1.png) | Not acquired |
| Trust | [Plot](figures/group-6647ebcd26e0-page-1.png) | Not acquired |

- [All 32 PNG plots](figures/), covering all four echoes and acquired task/session groups.
- [HTML dashboard](index.html). GitHub displays source; download this full
  directory and open index.html for the rendered dashboard and working links.
- [Validation](validation.json), [scope](report_scope.json), [methods](methods.md).

## Validation

Strict artifact/completeness verification passed for this functional scope:

| Measure | Result |
| --- | ---: |
| Applicable magnitude images / MRIQC matches | 11,196 / 11,196 |
| Unresolved MRIQC matches | 0 |
| Identity/metadata issues | 0 |
| Missing core metrics | 0 |
| Orphan MRIQC results | 0 |
| Phase images explicitly not applicable | 11,192 |
| Total inventoried functional images | 22,388 |
| Participants represented in the inventory | 354 |

The 396 anatomical entries and their four historical duplicate-identity flags
are outside this view. The duplicate cleanup itself was independently verified
on Linux2; see the original report's closure notes. This report does not imply
that anatomical MRIQC was performed.

All 22,388 retained image rows, 67,176 metric-flag rows, 192 threshold rows
and 504 scanner-summary rows match the corresponding original functional
rows exactly. No thresholds or flags were recalculated. The snapshot's 853
flagged images remain review flags, not exclusion decisions.

## Settled Decisions Remain Authoritative

This generic inventory is not an approved analysis cohort. It still includes
the 13 raw runs from already source-excluded subjects 11753 and 11836, exactly
as in the original inventory. Their presence does not reinstate them. All
2,786 canonical runs previously matched the original echo-2 metrics and
tSNR/FD flags exactly; those values remain unchanged here.

MRIQC smoothness describes the MRIQC input images, not AFNI's 6-mm smoothing
evaluation of fMRIPrep outputs. Source validity, approved cohort membership,
paper-specific coverage decisions and other settled exclusions are not changed.

## Reproduction

With the updated TUBRIC QA package, generate into a new sibling directory:

```bash
python -m tubric_qa.cli replot qc/tubric_qa --functional-only --strict \
  --output work/tubric-qa-functional-reproduction
python -m tubric_qa.cli check work/tubric-qa-functional-reproduction --strict
```

No BIDS indexing or MRIQC execution is involved. Original analysis provenance
is retained in source_provenance.json; the new provenance separately records
rendering code/dependencies, functional scope and omitted image receipts.
Live-input validation was not rerun on the Mac. Data-specific reports remain
in RF1; the reusable tubric-qa repository contains only code, tests and documentation.
