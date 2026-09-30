# Reviewed Shared Reward repair: Linux2 runbook

The PI-approved interpretation and behavioral hashes are in
[10668-task-reconstruction.md](10668-task-reconstruction.md). The script is
implemented and synthetically tested; **the live Linux2 repair has not yet run**.

## Scope

- `10657`: downstream `sharedreward-aging/docs/curated_run_exclusions.tsv`
  excludes RF1 session 01 run 1 only, for the incorrect displayed friend name.
  Run 2 remains eligible on source-validity grounds. No BIDS deletion or Trust
  exclusion is introduced. Regenerate the downstream analysis cohort after pull.
- `10668`: preserve Trust run 1; relabel the second Trust-labeled acquisition as
  Shared Reward run 1 using attempt A and the first 255 volumes; relabel the old
  Shared Reward acquisition as run 2 using B. Both retain scheduled design 1.
- No QA-based exclusions, cohort-wide reconversion or production TEDANA method
  change. Existing task models and simultaneous nuisance regression are unchanged.

## Before running

Stop all jobs and downstream readers using sub-10668. Do not run a separate
MRIQC/fMRIPrep/TEDANA process while this workflow runs. The `--confirm-idle`
flag attests to this operator check; the script cannot see other users' remote
analysis processes. A fMRIPrep lock and a separate rebuild lock prevent common
accidental overlap. No SSH execution is performed by the local assistant.

Required: the existing private September 16 inventory at its original path,
saved HeuDiConv edit/seqinfo/filegroup files, current private behavior, nibabel,
numpy and pandas in the pinned TEDANA environment, plus ordinary pipeline tools.
The inventory and both behavioral inputs must match their reviewed SHA-256s.
Missing evidence, conflicting targets, unexpected lengths, native geometry or
available acquisition-parameter differences (except run-local slice timing)
stop the repair before live changes.
Unavailable metadata is reported, never described as a verified match.

### September 30 preview correction

The first preview stopped at an exact cross-acquisition `SliceTiming` equality
check, before modifying data. That check was an implementation error, not proof
of an unusable acquisition. The log did not include the timing values, so it
does not establish the size or cause of the difference.

Each acquisition is processed separately by
[fMRIPrep](https://fmriprep.org/en/25.2.5/workflows.html), using its own timing.
The repair now validates every available magnitude/phase echo's timing array
against its own image: finite numeric values within the TR, slice count and
declared slice axis. An undeclared axis uses the NIfTI slice axis, or a uniquely
matching image dimension for count validation; ambiguous dimensions stop the
repair. Repeated timing values are allowed for simultaneous slices.

The preview reports first-magnitude-echo timing counts, ranges, axis evidence
and the cross-run maximum absolute difference in seconds (voxel-index order).
These are diagnostics, not evidence of identical acquisition parameters or
behavioral synchronization. No tolerance is used to dismiss a difference.
`SliceTiming` and `SliceEncodingDirection` remain unchanged for each source
image, including all echoes and the cropped run. No timing is copied from the
other run, rounded, or synthesized; slice-timing correction is not disabled.
Negative slice direction is interpreted only for the diagnostic comparison,
following the [BIDS MRI specification](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/magnetic-resonance-imaging-data.html).
Other acquisition guards and the full derivative rebuild remain in place.
Review the new preview before applying; the live difference still needs to be
read from that output, not inferred from synthetic tests.

### Preview and apply

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
umask 0000
mkdir -p logs/runs
bash code/run_logged.sh --label "10668-repair-preview-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- bash code/run_10668_rebuild.sh --dry-run
```

Expect the reviewed two-acquisition mapping, an explicit derivative archive list,
and `DRY RUN: no files changed`. Review that output before the next block.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
STAMP=10668-reviewed-rebuild-$(date +%Y%m%d-%H%M%S)
nohup setsid -f -w bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  bash code/run_10668_rebuild.sh --apply --confirm-idle \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "$STAMP"
sleep 5
tail -40 "logs/runs/${STAMP}.nohup.out"
```

The runner checks BIDS/events, rebuilds WarpKit and IntendedFor, MRIQC, fMRIPrep,
then audits/verifies geometry, runs production TEDANA, generates combined
confounds, and checks 255-volume/row alignment for both Shared Reward runs.
It stops on any failed stage. Geometry outliers are not automatically resampled.
MRIQC and fMRIPrep select new repair-specific scratch directories, preserving
old caches without using them. FreeSurfer anatomy is retained. The default
resources remain those configured for ordinary subject processing.

## Preservation, repeat runs and failure handling

The ignored archive is `derivatives/source_repairs/10668-sharedreward-v1/`:

- `original_session/`: the complete pre-repair BIDS session, including old events
  and fieldmaps, verified against its pre-repair file hashes.
- `original_heudiconv/`: saved conversion evidence. Live HeuDiConv metadata is
  intentionally not rewritten to pretend the original conversion had new labels.
- `retired/derivatives/`: whole-subject production fMRIPrep, MRIQC, WarpKit,
  TEDANA and combined-confound outputs that existed before correction, plus
  subject HTML reports. They are outside the production discovery roots.
- `receipt.json`: state, input hashes, retired paths and corrected file hashes.
  The session `.rf1-10668-repair.json` records the correction overlay. Native
  protocol/series metadata remains unchanged; TaskName reflects corrected task.

No raw DICOM or private behavioral file is edited. No outside analysis repository
is automatically cleared. Existing downstream results/manifests are stale until
regenerated; do not use them as evidence of completion. Cohort QC snapshots and
experimental TEDANA audit branches also require an explicit later refresh if
they are to include this corrected acquisition.

An already completed repair verifies recorded outputs/backups without applying
the swap again. The rebuild runner can then resume ordinary processing. An
interrupted repair receipt **fails closed**: preserve all files, stop readers,
and inspect the recorded state before recovery. Do not delete the archive or
blindly rerun prepdata; a partial derivative retirement or session installation
needs reconciliation. A stale rebuild lock after a machine crash must only be
removed after confirming the process is gone.

`prepdata.sh` applies the same transformation inside disposable staging for a
future from-scratch conversion of 10668 session 01, requiring the reviewed private
inventory. It refuses to overwrite an existing canonical 10668 session so this
cannot silently undo the correction or bypass derivative invalidation. Retain
the private inventory with acquisition provenance for future regeneration.

## Completion and handoff

The final success message is:

```text
CHECK PASSED: 10668 rebuild complete. Refresh cohort QC/analysis manifests before downstream analysis.
```

Share the new `logs/records/*10668*.md` record, not the private archive or inventory.
Then refresh the cohort run QC/response-QC products and Shared Reward input/cohort
manifests under their existing workflows. Pull `sharedreward-aging` before
rebuilding its cohort so 10657 run 1 is excluded and run 2 is not. Review that
10668 contributes one Trust run and two appropriately paired Shared Reward runs;
the old Trust-run-2 entry must not remain in active inputs. Final QA is separate.
