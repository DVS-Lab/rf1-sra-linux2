# 10668: presented-task reconstruction, 2026-09-29

**PI-approved reconstruction; repair applied September 30; final validation pending.** After Ryan's clarification
and the PI's acceptance in the supplied Slack exchange, the source-validity
decision is settled. This is a reviewed historical interpretation, not an
independent timestamp proof. Scanner protocol labels describe the selected
sequence, not necessarily the stimulus displayed in this cross-computer incident.
The original September 29 documentation pass changed no live data. The September
30 run subsequently installed the reviewed repair and rebuilt derivatives through
confound generation. A headerless-table counting bug stopped the final checker;
use the [validation-only recovery](10668-repair-runbook.md#september-30-live-status-and-validation-only-recovery).

## Approved reconstruction

Times are relative to the first functional acquisition's start, from the
[September 16 inventory](../logs/records/20260916-000438_sharedreward-source-validity-20260916-000438.md).
Duration is N x TR, not the observed last-header timestamp.

| Episode | Magnitude/phase series | Scanner label | Volumes | Relative start (s) | Most likely presented attempt |
| --- | --- | --- | ---: | ---: | --- |
| 1 | 8/9 | Trust run 1 | 280 | 0 | Trust operator run 1, saved as raw run-0 |
| 2 | 11/12 | Trust run 2 | 280 | 687.883 | First Shared Reward attempt, while Trust was running on the other computer |
| 3 | 14/15 | Shared Reward run 1 | 255 | 1275.990 | Second Shared Reward attempt, repeating the run-1 design |

The interpretation in the last column assumes the participant viewed L2 and
that computer's task started on the corresponding scanner trigger. The PI has
accepted that reconstruction on the available evidence, without a surviving
absolute trigger record; it is no longer an open request for operator confirmation.
Either Shared Reward attempt fits any 280-volume episode by duration alone.
The chronology plus reported incident makes episode 2 the plausible first
Shared Reward acquisition, not duration or protocol naming. The lone Trust
attempt most plausibly belongs to episode 1; files alone do not prove display
routing during either Trust-labeled episode.

The tracker wording supplied by the PI says Trust run 2 was running on L3 while
Shared Reward was playing on L2. This is affirmative evidence of simultaneous
different task programs, not just an absent log. It does not explicitly identify
the participant's displayed computer or establish trigger alignment. The older
workbooks are no longer present at their supplied local paths, so this pass
attributes that wording to the PI's transcription rather than claiming a fresh
workbook inspection. There is no evidence here that the scanner acquisition was
cut short for time: both Trust-labeled scans have all 280 volumes. A decision to
omit a Trust task execution is a different fact.

## Behavioral inventory and historical numbering

One complete **42-trial Trust attempt** is available at
`Scan-Investment_Game/logs/10668/sub-10668_task-trust_run-0_raw.csv`.
It is byte-identical to acquisition commit `8c3b66ea6`, SHA-256
`4efedc6078779b77b993999ef6f35331c029764032c3cf0ecdd51b5012b2fffc`.
Historical `investment_game.py` explicitly saves operator run 1 through
`do_run(0, trials_run1)` and operator run 2 through `do_run(1, trials_run2)`.
Thus raw run-0 is the first Trust task design, not an extra preliminary run.
No second Trust trial log was found in the subject's current or all-ref path
history. This does not exclude an uncommitted or differently labeled file on
the acquisition computers. Ratings and design files are not additional attempts.

There are **two distinct complete 54-trial Shared Reward attempts**. Both match
the scheduled run-1 design, not different counterbalanced run designs:

| Attempt | Current split filename | First decision (s) | Last outcome offset (s) | Final fixation offset (s) | Source SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| A | raw run-1 | 4.035225 | 402.54376 | 412.0003 | `cc23b38f37104a22fb43b3d8ff1147ff0c7c8e6df9d2777a8f74b7862866deb7` |
| B | raw run-2 | 4.0221868 | 402.5614 | 412.0008 | `3f85c5f1d9c32a19fbd389f87c9bf2bfa0e8edfd10c24681cb9fb6dfbd087546` |

Acquisition commit `8c3b66ea6` already contains A then B in one raw run-1 CSV,
with repeated headers at zero-based lines 0 and 55. That original is
byte-identical to the preserved `.csv~` (SHA-256
`d5ad49f128ddcbc4542e2403ebbbb589ca6a60e8153c8af6670b561581ed3d42`).
The later split in `3f530e1e8` preserves every parsed field of A as raw run-1
and B as raw run-2. A and B have different timing/response data: they are not
duplicate exports of one attempt. No additional subject-specific trial logs were
found in current/all-ref history; the ratings file is not a third attempt.

The historical Shared Reward code selects the design and log filename from the
one-based operator selection before its internal `enumerate` loop. Its internal
zero index does not make raw run-1 a zero-based label. Both attempts originally
used operator run 1. The later run-2 filename is a curation label.

Append order is strong evidence of attempt order under normal execution: the
script saves at the end of the run, and PsychoPy's
[TrialHandler saveAsWideText](https://psychopy.org/api/data.html)
appends by default. The original committed append order, not merely the later
filenames, supports A before B. There is no absolute task timestamp or trigger
identifier saved in these trial rows. `studyStart` is the near-zero reading
after a clock reset, not wall-clock time. Therefore file order supports A/B
chronology but still cannot independently tie A to scanner episode 2.

**Required correction:** current canonical Shared Reward run 1 resolves to
A under the filename convention, while its BOLD source is series 14 (episode 3).
The approved reconstruction instead pairs A with episode 2 and B with episode
3. It requires correcting that existing pairing as well as recovering the
other run. This note does not implement either change. The confirmed source UID
links did not certify the presented task or event/BOLD alignment.

## Imaging parameters

The tracked `qc/tedana_audit/current_runs.tsv` and scanner-era echo table show
all three episodes have TR approximately **1.615 s**, four echoes at
**13.80, 31.54, 49.28, 67.02 ms**, Siemens Prisma, 3 T, and syngo MR E11.
The scan durations are **452.200 s** (280 volumes) and **411.825 s** (255).
Their duration difference is **40.375 s**, exactly 25 TRs.

At the original September 29 review, full imaging-parameter identity was **not
yet established locally**. Native
matrix/voxel geometry, orientation, slice timing, flip angle, acceleration,
readout and phase-encoding details are not all in the tracked subject-level
tables. Matching the MNI output grid would not prove those acquisition settings
were identical. The existing private inventory includes all three runs' BIDS
sidecars; compare it without collecting DICOMs again. The optional audit below
reports equality/difference/missingness for a whitelist, never raw identifiers.
Native image geometry still needs live NIfTI headers if absent from sidecars.

September 30 update: the live repair validated matching native geometry and the
guarded acquisition parameters. Both runs have 51 slice timings spanning 0-1.5 s;
their maximum timing difference is 0.0025 s. They are not identical timing arrays:
each acquisition retains its own array for its separate preprocessing workflow.

## Actual task-design test: no trimming required for estimability

Local FSL `feat_model` tests used each complete attempt through Linux2's actual
behavior converter, the pooled repository's actual full-trial harmonizer,
activation renderer and 28-contrast contract (`sharedreward-aging` `79ee586`).
All intermediate EV/FSF/design files were temporary. Only task EVs were included;
no synthetic confounds or BOLD fitting were used. Existing HRF/filter settings
were preserved. Tests assume correct scanner-trigger time zero.

| Attempt | Volumes | Task matrix | Task rank | Rank with intercept | Retained contrasts estimable |
| --- | ---: | --- | ---: | ---: | ---: |
| A | 255 | 255 x 10 | 10 | 11 | 22/22 |
| A | 280 | 280 x 10 | 10 | 11 | 22/22 |
| B | 255 | 255 x 10 | 10 | 11 | 22/22 |
| B | 280 | 280 x 10 | 10 | 11 | 22/22 |

Maximum retained-contrast row-space projection error was below `1e-14`.
The 280-volume task-plus-intercept model has 269 nominal algebraic residual
degrees of freedom, before the real nuisance matrix and autocorrelation effects.
Both attempts have nonempty reward/punish conditions for every partner. This
establishes task-only estimability, not full nuisance-GLM or PPI acceptance.

The historical script transitions from final fixation to an exit screen after
approximately 412 s. Therefore the extra approximately 40 s need not be resting
fixation. The PI-approved choice is to retain the first 255 volumes, matching
the intended Shared Reward acquisition window and removing the extra tail.
This is not a QC-based exclusion or a requirement for estimability. The retained
window ends at 411.825 s, after both attempts' last recorded outcome at about
402.55 s; it matches the ordinary 255-volume run, not a claim that the full HRF
has decayed. Preserve originals and align all time-dependent products.

## Review closure and engineering handoff

Ryan's supplied follow-up interprets the note about rerunning Trust rather than
claiming certain recall, and explicitly supports relabeling the second Trust
scan as Shared Reward run 1. David V. Smith accepted this interpretation and
approved proceeding. The chronology wording remains imperfect; preserve this
evidence limitation without asking the team the same question again. No claim
that time pressure motivated the incident is needed for the repair.

Approved target products:

| Original canonical acquisition | Target | Temporal selection | Behavioral source |
| --- | --- | --- | --- |
| Trust run 1, series 8/9 | Trust run 1, unchanged | All 280 volumes | Trust raw run-0 |
| Trust run 2, series 11/12 | Shared Reward run 1 | First 255 volumes: zero-based `[0:255]`, discard final 25 | Shared Reward attempt A |
| Shared Reward run 1, series 14/15 | Shared Reward run 2 | All 255 volumes | Shared Reward attempt B |

The two Shared Reward run numbers denote corrected acquisition order. Both
attempts used the scheduled run-1 design; do not relabel the second attempt's
experimental design as the scheduled run-2 design.

The implementation is available in the [Linux2 runbook](10668-repair-runbook.md).
It has synthetic tests. The checklist below describes the complete repair scope;
the September 30 run completed application and processing, with final alignment
and post-rebuild events validation still pending as described above:

- Verify exact source identities, behavioral hashes, image lengths and native
  acquisition parameters before writing; the saved sidecar comparison below
  completes part of this engineering preflight, not another lab decision.
- Preserve immutable originals and hash-bound provenance for the acquisition,
  behavior, review decision and `[0:255]` selection. Never edit raw DICOMs or
  private source logs. Keep identifying header metadata outside Git.
- Stage the old Shared Reward run 1 before assigning the recovered run to that
  path; fail on conflicting targets and make resume/idempotency explicit.
- Implement the same mapping in regeneration from source, not just a one-off
  rename. Inventory magnitude/phase echoes, SBRefs, JSON metadata, scans records,
  fieldmaps and IntendedFor associations so task labels remain consistent.
  Apply temporal trimming only to the affected 4D series, not static SBRefs/masks.
- Retire stale affected derivatives from active discovery with preserved
  provenance, then regenerate the necessary preprocessing, TEDANA, confounds,
  event exports and QC inventories. Do not merely rename old derivatives or
  assume a cropped old ICA solution equals a new 255-volume decomposition.
- Verify one retained Trust run and two correctly paired Shared Reward runs,
  255-volume/row alignment for affected products, intended fieldmap associations,
  canonical downstream paths, and absence of the stale Trust-run-2 analysis entry.
  Record the final Linux2 run/check logs before marking the repair complete.

This checklist is not an executed repair. Data-quality adjudication remains a
separate later step; no motion, behavioral-performance or mask-coverage rule is
introduced here.

## Reproduce and complete the parameter check on Linux2

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
bash code/run_logged.sh \
  --label "10668-hypothesis-$(date +%Y%m%d-%H%M%S)" --include-full-log -- \
  /ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python \
  code/audit_10668_hypothesis.py \
  --behavior-root /ZPOOL/data/projects/rf1-sra/stimuli \
  --sharedreward-root /ZPOOL/data/projects/sharedreward-aging \
  --inventory work/sharedreward-source-validity-20260916-000438/inventory.json
```

Requires FSL `feat_model` on PATH. No imaging analysis, conversion, trimming,
renaming, source repair or eligibility update is performed. Only the redacted
run record should be shared. Original workbook paths were unavailable locally;
operator-note interpretation above uses the wording supplied in the request.
