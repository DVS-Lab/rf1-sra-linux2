# Task Availability Reconciliation

## Scope

This is a read-only engineering audit for the Katie/Social Doors and Sophia/UGR
handoff. It does not freeze either paper sample, change any imaging data, clear
review holds, or turn QC outliers into exclusions. Do not send a final cohort
recommendation until the Linux2 audit and its verification have been reviewed.

The default scope is every ID in live `bids/participants.tsv`, session 01 only:
Social Doors run 1 and UGR runs 1 and 2, including expected runs with no events.
An optional IDs-only `--sublist` can later select the exact linked paper cohort.
Do not reconstruct that cohort from exclusion-only lists or infer its membership.
Session-02 additions do not substitute for missing baseline runs. An explicit
`--sessions 01,02` inventories both waves separately.

## Separation Of Evidence

- `roster_gate` respects the authoritative private source-exclusion directory,
  even if residual outputs exist. Per-ID details remain under ignored `work/`.
- `existing_hold` transcribes the existing UGR 11201 run-1 model-3 hold. It is
  not cleared by a file-presence check or a QC pass. This small scoped table is
  not a replacement for the broader RF1 decision record.
- Optional `--dispositions FILE` carries existing reviewed decisions verbatim.
  Required columns: subject, session, task, run, decision, reason, evidence.
  Accepted decisions: include, exclude, review, unavailable. Even an include
  does not waive technical checks or the authoritative participant exclusion.
  A newly installed `qc/run_disposition.tsv` must be supplied explicitly rather
  than silently ignored. Other-task decisions are not broadened to these tasks.
- `technical_status` reports current canonical BIDS/BOLD/events/confound
  presence, image header validity, event timing, and image/confound row alignment.
  Absence is not a finding that the task was never acquired. Permission errors
  abort rather than being reported as missing data.
- `prior_manifest_state` compares the current task repositories' saved
  `logs/runlists/L1-ready.tsv` and `L1-missing.tsv` when available. These snapshots
  are hashed, not overwritten. No subject-specific exception is needed for 12018.
- `recorded_*` preserves the existing QC measurements and flags unchanged.
- `task_session_*` recalculates descriptive flags using policy v2 and the full
  approved MRI roster's recorded measurements, never the selected paper cohort.
  The four metrics, one-pass linear quartiles and 1.5 IQR multiplier are unchanged.
  Exact BIDS task and session define the threshold population. Doors and Social
  Doors are separate. Scanner eras are descriptive strata, not new thresholds.
- FEAT checks inspect activation model-1 Social Doors and model-3 UGR, including
  all declared contrasts (17 for UGR), COPEs, VARCOPEs, Z statistics and design
  files. They record L1 input-path agreement and UGR L2 presence separately.
  File presence does not certify model rank, full voxel integrity, contrast
  interpretation, or hash lineage to current inputs. No L1/L2 selection is made.
- `final_analysis_eligibility` is always `not_assigned_by_audit`.

## Linux2 Command

After the code update is available on Linux2, run from the project root:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
STAMP=task-availability-$(date +%Y%m%d-%H%M%S)
PRIVATE="work/$STAMP"
bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  "$AUDIT_PYTHON" code/audit_task_availability.py --private-dir "$PRIVATE" \
  --check "$AUDIT_PYTHON" code/audit_task_availability.py \
    --private-dir "$PRIVATE" --check
```

Only the aggregate run record is suitable for committing. Do not force-add
`work/`. The private directory contains `run_review.tsv`, `summary.tsv`,
`task_session_thresholds.tsv` and `provenance.json`. A successful exit means
the audit completed; missing runs and QC flags are findings, not audit failures.
The checker validates unique keys, hashes, current input states, image/text input
size/mtime, text hashes, exclusion inventory, and FEAT output presence/designs.

This command reuses stored QC measurements; it does not rerun MRIQC, TEDANA or
coverage extraction. If recent processing changed those inputs, a separately
validated QC rebuild is needed before final adjudication. The new policy makes
older pooled QC artifacts historical until regenerated. Do not describe the
old `qc_status` as a task/session-specific exclusion decision.

## Verification Before Handoff

1. Review all technical findings and differences from prior snapshots.
2. Resolve missing/stale measurement rows separately from metric outlier flags.
3. Inspect current-model provenance where only output presence is established.
4. Join Jacob's exact linked cohort when available; do not claim to reproduce
   118, 82 or 90 from the full MRI roster.
5. Review task-level scientific QC decisions separately. Preserve all settled
   source-validity exclusions throughout. No message to Jacob has been sent.

## Verified Manifest Refresh

`code/refresh_task_handoff.py` builds a fresh audit and invokes the updated
UGR and SocDoors builders against the full MRI roster. Both builders enumerate
every expected run, including absent sessions/events, and require the private
source-exclusion root. The handoff checks exact coverage and duplicate keys,
then partitions runs into `L1-ready.tsv`, `L1-missing.tsv`, and `L1-held.tsv`.
Existing holds and any supplied reviewed dispositions take precedence over file
presence. Source-excluded residual data cannot enter the ready list. QC flags
are not used to decide membership of any of these technical lists.

This refresh is scoped to session-01 Social Doors and UGR. It writes new,
dated manifests under private `work/`, not over the historical task-repository
`logs/runlists` snapshots. This avoids erasing Doors or other-session rows and
preserves evidence of the stale inventories. Use the new explicit paths for
the handoff; do not keep using the old snapshots or a 12018-only exception.
Raw builder outputs are diagnostic inventories only. The exported subdirectory
manifests, after a successful check, are the ones with reviewed holds applied.

Pull all three repositories before running:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
STAMP=task-handoff-$(date +%Y%m%d-%H%M%S)
PRIVATE="work/$STAMP"
bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  "$AUDIT_PYTHON" code/refresh_task_handoff.py build --private-dir "$PRIVATE" \
  --check "$AUDIT_PYTHON" code/refresh_task_handoff.py check --private-dir "$PRIVATE"
```

An installed `qc/run_disposition.tsv` is not silently ignored: supply
`--dispositions qc/run_disposition.tsv` to build. This follows the audit's
explicit-decision contract. Optional decisions use subject, session, task, run,
decision, reason, evidence; include never overrides a technical failure or hold.

Private outputs:

- `ugr/L1-{ready,missing,held}.tsv`: standard UGR run-key columns, plus reason
  for non-ready rows. A missing L2 is not an automatic exclusion of a single run.
- `socialdoors/L1-{ready,missing,held}.tsv`: standard four-column SocDoors keys,
  plus reason for non-ready rows. Does not include or substitute Doors.
- `run_review.tsv`: every expected slot with prior-manifest status, original and
  exact-task/session QC flags, decisions, technical findings and L1/L2 evidence.
- `summary.tsv`, `provenance.json`, `audit/`, and private command logs.

Check verifies output/source hashes, all expected run keys, live input state,
and the original audit's provenance. Re-running build requires a new directory.
The refresh does not run FEAT, generate EVs, modify canonical QC, select L1 vs L2,
or freeze a paper sample. Output presence/path checks do not establish FEAT
current-input hash lineage. The exact 118-ID paper roster is still needed for
paper-specific counts. Commit only the aggregate run record, never `work/`.
