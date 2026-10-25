# Install Reviewed Repairs

## October 25 FEAT Archive Stop

The `20261025-093440_reviewed-install-v2-20261025-093440` record exited 1
during planning while inventorying the old 11935 Social Doors FEAT output's
`reg/standard.nii.gz` link. Both staged-payload checks were reached, but the
installation transaction never began; no production images were replaced.

The v3 bundle inventories retired FEAT file and directory symlinks without
following them, preserves their exact link text in the archive, and verifies
that text before unlinking the original directory entry. Dangling links are
also preserved. External link targets are never copied, modified, or deleted.
This exception applies only to retired downstream outputs; replacement payloads
and their destination parents retain strict no-symlink checks. Tests cover the
reported FEAT layout, directory links, dangling links, target preservation,
archive tampering, and special-file rejection.

## October 24 Installation Stop

The `20261024-234356_reviewed-install-20261024-234356` record exited 1 during
read-only planning, at FreeSurfer's `surf/lh.white.K` symlink. Installation
never began; no production images were replaced and the checker was skipped.
This was an installer inventory-policy bug, not a failed reconstruction.

The v2 transport bundle observes FreeSurfer links using the original validator's
read-only file-stat semantics. FreeSurfer is excluded from the install payload;
its production files and link topology are checked before/after installation.
Replacement-file and destination symlinks are still forbidden. No links are
deleted, rewritten or dereferenced into the install payload. Use a fresh v2
tools directory with the same still-uncreated transaction archive. If that
archive does exist, stop for inspection rather than deleting it.

This is the installation-only closeout for 10964 ses-02 (Doors, Social Doors,
UGR runs 1 and 2) and 11935 ses-01 (Doors and Social Doors run 1). Both staged
repairs must have their final validation receipts. The reviewed 11935 images
have 99.55% Doors and 99.42% Social Doors canonical coverage. This image review
does not reverse any settled exclusion, including 11935's paper exclusions.

The original cohort experiment finished with 8,343/8,343 outputs and no findings.
Do not run `run_11935_completion.sh promote` for this installation: that older
workflow revises the experiment rather than preserving it as a completed study.

## Scope

`code/install_reviewed_repairs.py` uses only the standard Python library and
the adjacent `code/promote_11935.py` safety helpers. It does not invoke that
older module's apply function. It preserves umask 0000, acquires the actual
cohort/stage/downstream/subject locks, and fails on a busy lock. It neither
terminates processes nor removes another process's locks.

It validates staged receipts, hashes the six runs' functional products, merges
only their scans.tsv rows, and archives every replaced production file before
the first live mutation. Replacement files are installed without clobbering
unexpected files. It retains session-01 data for 10964, anatomy, FreeSurfer,
participants.tsv, all QC outputs, curation, holds and exclusions. The isolated
workspaces remain intact as processing provenance. Whole-subject HTML reports
are not replaced with reports for incomplete isolated datasets.

Affected existing L1/L2/EV/timeseries products in UGR and Social Doors are
archived, not silently left at canonical paths after their inputs change.
The installation receipt lists these under `downstream_requires_rebuild`.
This command does not rebuild models, change eligibility, refresh QC/handoffs,
or rerun L3. L3 results incorporating an affected run need separate review;
11935 remains excluded from the two current papers, and 10964's installation
affects ses-02 only, not those papers' ses-01 imaging pools.

## Historical Cohort

The experiment's manifest, validation, summaries, success receipts and results
are untouched. Its existing validation describes the PRE-REPAIR inputs.
All original inputs for affected manifest rows are copied and hash-verified in
the installation archive. `historical-cohort/input-lineage.json` maps the old
production-relative paths to these copies. The manifest and validation are
also copied into that archive. Unchanged experiment files are checked by
size/mtime before and after installation; this is not a new scientific run.

Do not resume/check the old cohort runner against newly installed production
paths: its strict signature checks should reject changed inputs. A future
comparison on repaired data must be a separately versioned experiment, using
the preserved results only where input identity is established.

## Delivery And Execution

A transport bundle can be made without committing/pushing or updating Linux2's
tracked checkout. It contains this runbook, the installer, its safety helper,
and the existing log publisher. Transfer it from the Mac to Linux2, extract to
a new ignored work directory, then run from the production project root:

```bash
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
python3 work/reviewed-install-v3/code/install_reviewed_repairs.py install \
  --project "$PWD" --archive "$PWD/work/reviewed-install-archive-v1" \
  --approve-images
python3 work/reviewed-install-v3/code/install_reviewed_repairs.py check \
  --project "$PWD" --archive "$PWD/work/reviewed-install-archive-v1"
```

Use `code/run_logged.sh` around the install and check (see chat's complete
launch commands). File copying/hashing may take time; it is not preprocessing.
Success requires BOTH checks and exit 0. The installer refuses an existing
archive. On interruption, preserve the archive, journal and temporary files;
do not delete them or blindly rerun install. Use `check` only for a completed
installation; an incomplete journal stops explicitly for recovery.

Publish the finished run record without adding/committing or pulling:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
python3 work/reviewed-install-v3/code/publish_run_logs.py --project "$PWD"
```
