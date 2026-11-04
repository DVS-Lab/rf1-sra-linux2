# Full-Sample Social Reward Inventory

This is a separate exploratory paper inventory for loneliness, Need to Belong,
depressive symptoms and continuous adult age. It does not change the frozen
97-person environmental/financial-vulnerability study, any running jobs,
preprocessing, existing exclusions, or previous registrations.

## Initial Scope

- Begin with all adult ages, not the age-55+ paper roster or recruitment target.
- Inventory baseline paired Social Doors/Doors first. Report ses-02 separately.
- Do not require ADI, PM2.5, MSPSS, FEVS, OAFEM or Ecog completeness.
- Preserve source-validity decisions and existing run-level QC rules. A ses-02
  flag cannot exclude ses-01. Both constituent runs matter to a paired contrast.
- Inventory instruments and source/visit linkage before choosing new models.
  Depression is a central construct, not automatically a nuisance covariate.
- Do not launch inference or new interaction families during this inventory.

The current task outcomes remain distinct:

1. Domain by valence: `(social win - social loss) - (monetary win - monetary loss)`.
2. Social win minus monetary win, not wins versus baseline.
3. Domain-average win minus loss: `[(social win - social loss) + (monetary win - monetary loss)] / 2`.

No new outcome hierarchy or analysis model is frozen by this document.

## Source Evidence

The older task repository's September 2024 covariate export contains
`uclal_score`, `nbs_adult_sum`, `susd_adult_depression`, and `sub_age`.
These establish that separate candidate scores existed, not their current
coverage, exact instrument versions, item validity or alignment to a scan.

The October 2026 environmental workbook is a purpose-specific, older-adult
complete-case export. Do not use it as the full-sample questionnaire inventory.
Jacob's environmental R script points to a private Windows screener export; it
does not establish that the latest full questionnaire source is on Linux2.

The local first pass on November 3 found 202 exact, unique RF1 IDs in that
September 2024 export (203 source rows, one invalid/missing RF1 ID):

| Candidate field | Finite exported values | Observed range |
| --- | ---: | ---: |
| `uclal_score` | 57 | 3-9 |
| `nbs_adult_sum` | 152 | 1.2-4.9 |
| `susd_adult_depression` | 182 | 0-21 |
| `sub_age` | 196 | 21.31-83.76 |

Only 39 records have all four populated in this old file. This is **not the new
paper N**, and a blank field is not evidence the questionnaire was never
collected. The fractional, 1-5-like values in `nbs_adult_sum` particularly need
the actual scoring definition; do not infer an item sum from that column name.
These aggregate counts have not been linked to an approved imaging cohort.

`inventory_lifespan_measures.py` uses only Python's standard library. It reads
CSV/TSV files and the existing canonical QC table; it does not index DICOMs,
read image pixels or run MRIQC/fMRIPrep/TEDANA/FEAT/randomise.

The tool:

- Searches table headers to depth four in explicitly supplied project roots,
  pruning `work`, `bids`, `derivatives`, `stimuli`, environments and symlinks.
- Profiles existing candidate score columns, distinguishing absent columns,
  missing tokens, nonnumeric values, duplicate IDs and suffixed ID aliases.
- Retains separate REDCap event summaries and never chooses a repeated record.
- Reports finite exported totals, **not validated or analysis-ready scores**.
  Numeric missing-value codes such as 999 cannot be adjudicated without the
  instrument dictionary. No item-level scores are recomputed.
- Uses age strata only to describe coverage, with no age-55 selection.
- Summarizes existing paired task QC records separately by session. These are
  **not source-valid or fully processed imaging Ns**. Source decisions, live
  input lineage, event alignment and lower-level availability remain to verify.
- Fingerprints profiled inputs and refuses to overwrite an inventory directory.
- Writes an aggregate private JSON report and sanitized log output, never
  participant-level scores, dates of birth, item responses or addresses.

The search is deliberately bounded. A zero search result does not prove that a
questionnaire was not collected; raw exports may be on a different machine, in
an XLSX workbook, or under excluded `work/`. Supply a known CSV/TSV explicitly
with `--survey /absolute/path.csv` when found.

## Linux2

Use a frozen read-only reporting release rather than pulling over an active
analysis checkout. The launcher preserves `umask 0000` and automatically
publishes the sanitized run record even if the inventory fails. No private
inventory is committed. HTTPS only; no SSH or file-transfer command is needed.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git -c remote.origin.url=https://github.com/DVS-Lab/rf1-sra-linux2.git fetch origin main
bash <(git show FETCH_HEAD:code/run_lifespan_inventory.sh)
)
```

The default header search covers `rf1-sra`, `rf1-sra-socdoors`, and
`rf1-sra-environment-SD` project trees. It does not search the whole ZPOOL.
The printed inventory directory is a new ignored `work/lifespan-inventory-*`
snapshot. `inventory-private.json` contains source paths, header candidates,
fingerprints and aggregate summaries, not an approved subject list.

## Still Required Before a Cohort Freeze

1. Locate current full-sample screener and RF1 questionnaire exports and REDCap
   dictionaries, including repeat/event and completion fields.
2. Establish the administered loneliness scale/version (do not substitute MSPSS),
   Need to Belong items/reverse keys, and the depressive Down subscale versus
   the manic Up subscale. Verify ranges, sentinel codes and missing-item rules.
3. Resolve repeated IDs and link survey waves/dates to baseline scans explicitly.
   Document the age reference date. Do not silently choose a first duplicate.
4. Reconcile all-age paired imaging against the approved roster, settled source
   decisions and live processing/output evidence. Existing age-55+ L1 bundles
   do not establish that younger adults have the same model variant available.
5. Then report valid-score overlap, age distributions, reliability and construct
   correlations. Distinguish measurement/linkage gaps from imaging exclusions.

No final full-sample N is assigned by this first-stage inventory.
