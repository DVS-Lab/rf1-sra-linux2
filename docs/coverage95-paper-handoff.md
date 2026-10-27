# Coverage95 paper handoff

**Superseded for paper selection, October 27, 2026.** This historical procedure
omitted intended FD and tSNR exclusions. Keep its outputs as provenance, but use
the [corrected FD/tSNR/coverage handoff](fd-tsnr-paper-handoff.md) for new L3 inputs.
No settled exclusion or completed processing is changed.

For Jacob's current validated paths, starting Ns, selection rules, and next
steps, use the [canonical paper handoff README](paper-handoff/README.md).
This page is the technical regeneration runbook, not a request to rerun completed jobs.

## Approved policy, 2026-10-21

The PI approved excluding individual baseline analysis runs with canonical
`brain_coverage_pct < 95.0`, preserving other eligible runs and tasks. Exactly
95 passes this coverage criterion. Missing, nonfinite, or impossible percentages
are withheld for review. This data-informed, post-review study rule replaces the
boxplot coverage flag for this no-TEDANA paper handoff only. It is not a universal
threshold, a preregistered criterion, or proof of adequate coverage in every ROI.
The fixed target is the existing QC reference excluding historical
cerebellum/brainstem regions; do not describe it as literally all brain tissue.

No canonical QC flags, source exclusions, BIDS files, FEAT outputs, or frozen
runner code are rewritten. Existing source/roster exclusions, run holds and
frozen reviewed dispositions remain binding. Additional explicit reviewed
decisions can be supplied with `--dispositions`; an include cannot override a
settled hold or rescue coverage below 95. Other QC flags (FD, TEDANA, tSNR) remain
visible but do not themselves become new exclusion decisions. Record any
approved exclusions based on these in the dispositions file, not by reusing an
old aggregate imaging-outlier flag.

Use paired UGR L2 only if both runs are eligible. Otherwise use the eligible
single-run L1, never a paired L2 that contains an excluded run. Social Doors and
Doors are separate analyses; neither is gated by the other's coverage. This
handoff does not select the combined Social Doors/Doors mean. Session 02 cannot
exclude a baseline run. There is no five-subject blanket exclusion.

## Linux2: validate and export imaging inputs

Wait for the existing no-TEDANA finish runner to complete. This step verifies
all frozen L1/L2 products and hashes; incomplete products stop it without
reprocessing anything. Hash/lineage checks can take time. Do not rerun prepare
or alter the existing plan to bypass a check. TEDANA can continue independently.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only

AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
FINISH="$PWD/work/no-tedana-finish-20261021-151127"
STAMP="coverage95-handoff-$(date +%Y%m%d-%H%M%S)"
HANDOFF="$PWD/work/$STAMP"
mkdir -p logs/runs
umask 0077

bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/handoff_coverage95.py build \
    --finish-dir "$FINISH" --private-dir "$HANDOFF" \
  --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/handoff_coverage95.py check \
    --private-dir "$HANDOFF"

printf '\nHandoff: %s\n' "$HANDOFF"
column -t -s $'\t' "$HANDOFF/counts.tsv"
```

Require `CHECK PASSED` and exit 0 before sharing. A successful check certifies
selection and lineage, not a final paper cohort or a new L3 fit. `run_logged.sh`
captures aggregate counts; participant-level lists stay in ignored `work/`.
Do not commit the handoff or private cohort inputs. No new task-repository code
is needed, and no L1/L2 jobs are launched by this command.

## Files for Jacob

All paths below are relative to the printed HANDOFF directory:

- `socialdoors/selected_inputs.tsv`: Katie task's imaging-eligible inputs.
- `ugr/selected_inputs.tsv`: Sophia task's imaging-eligible inputs.
- `doors/selected_inputs.tsv`: separately eligible Doors inputs.
- Each task's `subjects.txt`: unique imaging-eligible participant IDs.
- `run_decisions.tsv`: every reviewed run, numerical coverage, decision reasons,
  and unchanged descriptive QC flags.
- `counts.tsv` and `summary.json`: unique-subject counts, not contrast-row counts.
- `provenance.json` and its checksum: frozen sources, policy, and output hashes.

There is exactly one row per selected participant/contrast. Filter to the
intended contrast before building L3. Use the exact cope, varcope, mask and DOF
paths in that row; do not regenerate a paired-run path from the participant ID.
All paths point into the isolated no-TEDANA output trees. Rebuild and validate
L3 design/covariate row order after joining the cohort. Old L3 inputs/results
and old imaging-outlier aggregate exclusions do not represent this handoff.

Suggested handoff message after validation:

> Please use the validated coverage95 handoff at [printed HANDOFF path]. The
> Social Doors and UGR selected_inputs.tsv files contain the revised no-TEDANA
> inputs. Coverage exclusions are now run-level <95% of the fixed QC target,
> not boxplot outliers. Existing source-validity exclusions and reviewed holds
> remain enforced. Good UGR single runs are retained, and paired L2s containing
> an excluded run are not selected. Doors, Social Doors, and sessions remain
> independent. Other QC flags are descriptive unless backed by an explicit
> reviewed exclusion. Join the approved pre-imaging survey/linkage cohort to
> these IDs, not the previously QC-filtered final sample; select one row per
> subject for the intended contrast and rebuild the L3 design in matching order.
> Imaging Ns and paper Ns are explicitly distinguished in counts.tsv.

## Exact paper Ns

The frozen age-55+ imaging plan is known and used above. The approved paper
survey/linkage ID lists were not supplied to the previous reconciliation (see
`task-availability-reconciliation.md`); the historical 118 is a count, not an
identifiable roster. Neither the earlier 89/101 final samples nor an older
generic L3 subject list can substitute, because they would prevent recovery of
previously overexcluded participants. No code should infer membership from a
target N or guess which dated file is authoritative.

To locate candidate files on Linux2 without needing to recall their paths:

```bash
find /ZPOOL/data/projects -maxdepth 6 -type f \
  \( -iname '*katie*' -o -iname '*sophia*' \
     -o -iname '*cohort*.csv' -o -iname '*cohort*.tsv' \
     -o -iname '*participant*.csv' -o -iname '*participant*.tsv' \) -print
```

This lists paths only, does not choose a cohort, and is not an exhaustive search
of other mounts or deeper directories. Verify the generating script/stage and
approval before using a candidate; a final post-QC subject list is not suitable.

Once the approved **pre-imaging-QC** files are identified, run the same build
into a NEW private directory with `--katie-cohort /absolute/path/to/file.tsv`
and `--sophia-cohort /absolute/path/to/file.tsv`, followed by check. Optional
`--doors-cohort` supports a separate Doors paper roster. TSV/CSV files must have
one unique ID column named `subject`, `participant_id`, or `rf1_id`; sub- prefixes
are accepted, duplicates/invalid IDs are rejected. Extra survey columns are
not copied into the handoff. These options are explicit assertions that the
supplied rosters have already passed the approved non-imaging criteria.

```bash
# Set these to verified, approved pre-imaging cohort files, not old final samples.
: "${KATIE_COHORT:?Set approved Katie pre-imaging cohort path}"
: "${SOPHIA_COHORT:?Set approved Sophia pre-imaging cohort path}"
PAPER_STAMP="coverage95-papers-$(date +%Y%m%d-%H%M%S)"
PAPER_HANDOFF="$PWD/work/$PAPER_STAMP"
bash code/run_logged.sh --label "$PAPER_STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/handoff_coverage95.py build \
    --finish-dir "$FINISH" --private-dir "$PAPER_HANDOFF" \
    --katie-cohort "$KATIE_COHORT" --sophia-cohort "$SOPHIA_COHORT" \
  --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/handoff_coverage95.py check \
    --private-dir "$PAPER_HANDOFF"
column -t -s $'\t' "$PAPER_HANDOFF/counts.tsv"
```

`papers/katie/` and `papers/sophia/` then hold paper-specific selected inputs
and subject lists. `paper_membership.tsv` accounts for every supplied ID,
including IDs absent from the frozen imaging plan. Paper counts are conditional
on those supplied approved rosters and recorded dispositions; missing coverage
or other unresolved inputs appear as withheld, not as silently passed QC.

## Observed threshold effects, not paper N predictions

In the current canonical full-baseline UGR/Social Doors/Doors QC table, nine
runs across six participants fall below 95%. These are 11472 UGR r1 (XA30),
11622 Doors, 11692 Doors, 11701 UGR r1, 11935 Social Doors, and all four reviewed
runs of 11960. The 11472 and 11701 UGR run-2 values exceed 99%; those runs remain
coverage-eligible, subject to all other gates. This is a full-baseline inventory,
not a count of losses in either paper. The separate 11935 processing investigation
does not authorize production repairs or automatic inclusion in this frozen
handoff. Any later repair requires revalidation and a new handoff snapshot.
