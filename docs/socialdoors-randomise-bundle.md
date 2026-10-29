# Social Doors Minus Doors: Randomise Input Bundle

This packages the existing, verified age-55+, ses-01, no-TEDANA L1 estimates.
It does not run randomise, rerun L1/preprocessing, change UGR, modify images in
production, or reopen settled exclusions. The strict imaging pool has **121
participants**; that is not necessarily Katie's final survey/linkage cohort.

## Selection Is Already Settled

Both constituent runs must pass the existing source-validity decisions, mask
coverage >=95%, upper-tail FD and lower-tail tSNR task/session fences. The runner
authenticates the entire Git-shared `strict_pairs.tsv` against the checked
diagnostic, then optionally subsets it using an explicit final cohort. It never
adds flagged participants, recalculates fences, or drops unknown IDs silently.
There is no TEDANA-count or paired-effect-outlier exclusion.

## Build and Check the Imaging Pool on Linux2

Run checkout synchronization only after jobs using that checkout have stopped.
The helper preserves published logs and refuses unsafe checkout changes.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git fetch origin
python3 code/sync_published_checkout.py --project "$PWD" --apply --processing-stopped
bash code/run_socialdoors_randomise_bundle.sh pool
)
```

The wrapper runs build and an independent check, then publishes the run record
using `python3 code/publish_run_logs.py --project "$PWD"`, including when build
or check fails. A nonzero exit is not a validated handoff. Do not launch analyses
from partially built outputs. The work is image assembly and lineage checking,
not a new processing batch; it reads existing 3D estimates and assembles four
stacks serially, without launching FEAT or AFNI workers.

Output root:

```text
/ZPOOL/data/projects/rf1-sra-linux2/work/randomise-socialdoors-age55-pool-v1/
```

- `cope-1/difference_4d.nii.gz`: Social Doors win minus Doors win.
- `cope-2/difference_4d.nii.gz`: Social Doors loss minus Doors loss.
- `cope-3/difference_4d.nii.gz`: Social Doors decision minus Doors decision.
- `cope-4/difference_4d.nii.gz`: (Social Doors win-loss) minus (Doors win-loss).
- Each `cope-N/mask.nii.gz`: intersection of valid paired masks across the
  selected participants for that contrast. This is an analysis mask, not a new
  participant-level coverage exclusion. Mask voxel counts are in `counts.tsv`.
- `subjects.tsv`: exact volume order; `volume_index` is zero-based,
  `volume_number` is one-based. `cohort_ids.tsv` is the same ordered ID-only list.
- `qc_covariates_raw.tsv`: constituent FD, tSNR and coverage, plus derived QC.
- `qc_covariates_centered.tsv`: derived candidate covariates demeaned over this
  exact selected cohort, with the same IDs and volume order.
- `covariate_centering.json`: means, units, constant columns, candidate rank.
- `plan.json`, `plan.sha256`, per-contrast receipts and `artifacts.json`: source
  identities, cohort, policies and strong input/output hashes.

The effect stacks are float32 COPE differences, **not t/Z-statistic differences**.
They contain finite values inside the analysis mask and zeros outside it. Grids
must already match; the code never resamples. Original diagnostic maps are reused
and checked against the original L1 COPE/VARCOPE/mask data. VARCOPEs establish valid
support and provenance; the 4D stack is not variance weighted.

These estimates retain the original L1 **sm5** processing, not the experimental
AFNI 6-mm smoothness outputs. Completed images are preserved on resume; corrupt
receipted outputs fail rather than being silently overwritten.

## What Jacob Must Supply

For the final images/QC bundle, supply **one ordered ID-only TSV**, committed to:

```text
docs/paper-handoff/cohorts/katie-final.tsv
```

Its only header is `subject`; subsequent rows are unique five-digit RF1 IDs
(`sub-` prefix is accepted). This is Katie's approved survey/linkage cohort
intersected with the current strict 121-pair imaging pool, in the intended L3
order. Do not apply old TEDANA/coverage-only or pooled-task QC exclusions again.
Do not send DOB, names, or raw survey records. The builder rejects duplicate,
unknown, or ineligible IDs; it never silently reduces the cohort. If models use
different samples, supply a separately named roster for each model and build each
in a new output directory with the Python CLI.

The final cohort file does **not** exist yet. The pool bundle is useful now, but
must not be called the final paper sample. Once Jacob's file is committed and
available on Linux2, run:

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git fetch origin
python3 code/sync_published_checkout.py --project "$PWD" --apply --processing-stopped
bash code/run_socialdoors_randomise_bundle.sh final
)
```

Final output: `/ZPOOL/data/projects/rf1-sra-linux2/work/randomise-katie-final-v1/`.
The final check reports the exact N. Changing the roster after a build requires a
new output directory; never edit a frozen plan or manually slice an old stack.
The final rebuild reuses the diagnostic maps, recomputes the subset's common mask,
and recenters covariates for that subset. No L1 rerun is needed.

## Covariates Are Not Exclusions or a Finished Design

- `delta_fd` = mean FD Social Doors minus mean FD Doors (mm).
- `delta_tsnr` = tSNR Social Doors minus tSNR Doors (dimensionless).
- `pair_mean_fd` and `pair_mean_tsnr` capture overall pair quality; equal poor
  quality in both runs can yield a difference of zero.

These are candidate nuisance terms. The runner does **not** automatically put all
four into a model. Do not combine all original task metrics with their means and
differences: those columns are linearly dependent. QC covariates do not guarantee
correction of heterogeneous measurement error. Specify the model before testing
effects, rather than selecting nuisance terms based on significance.

To build the actual randomise design we additionally need Jacob's final
participant-keyed analysis-variable table, coding/reference levels and transforms,
planned image contrasts and statistical hypotheses, chosen QC terms, and any
family/repeated-measures dependencies requiring exchangeability restrictions.
Check full-design rank, missingness and exact row order before randomise. No
`design.mat` or `design.con` is guessed by this packaging step. See the
[official randomise documentation](https://fsl.fmrib.ox.ac.uk/fsl/docs/statistics/randomise.html).

All imaging inputs remain on the shared Linux2 filesystem. Use Git for the cohort,
shareable tables, documentation and validation logs; do not commit NIfTI stacks or
the entire ignored `work/` tree. No SCP/rsync is part of this workflow.
