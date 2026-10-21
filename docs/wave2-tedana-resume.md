# October 2026 Intake and Wave-2 Completion

## Reviewed Scope

The October 16 intake found six new ses-02 candidates. The five-subject
completion record (`20261016-205327_wave2-five-20261016-205327.md`) passed
through fMRIPrep for 11083, 11084, 11110, 11120, and 11193. The October 21
canonical QC refresh found these 20 runs missing TEDANA metrics. Its build
succeeded but its check failed; this was not a successful QC/handoff closeout.

10964 remains separate: its conversion attempt stopped at unresolved ses-02
Doors/Social Doors behavioral sources. Do not use ses-01 behavioral files as
wave-2 sources without resolving their provenance. This runner does not change
that hold or any settled exclusion.

## Fresh Intake

Run from `/ZPOOL/data/projects/rf1-sra-linux2` after pulling current code:

```bash
umask 0000
AUDIT_BIN=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin
STAMP=source-intake-$(date +%Y%m%d-%H%M%S)
bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  "$AUDIT_BIN/python" code/plan_source_intake.py \
  --private-dir "work/$STAMP"
```

This scans current source folders rather than relying on file modification
dates. It respects source exclusions and reports new-session candidates,
unrecognized layouts, and supplemental-source problems without converting
anything. Unknown folder names and detailed paths stay in the private inventory.
The October 16 inventory is not a complete per-file source snapshot: neither
that intake nor this fast scan can establish whether additional acquisitions
were downloaded into an already-converted session. Existing BIDS sessions are
explicitly reported as **not revalidated**, not as complete. Any such additions
require a separate acquisition inventory and conversion-provenance review.

## Resume and Verify

Do not start overlapping TEDANA/confound/QC writers. This runner uses a Linux
`flock` to prevent a second instance of itself, not unrelated manual jobs.
Its default is four concurrent subject jobs, adjustable with `TEDANA_JOBS`.
The default Python/TEDANA paths use the pinned 26.0.3 environment.

```bash
bash code/resume_wave2_tedana.sh --dry-run
STAMP=wave2-tedana-finish-$(date +%Y%m%d-%H%M%S)
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  bash code/resume_wave2_tedana.sh \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "STAMP=$STAMP"
```

The preflight requires exactly four acquired runs per selected subject, all
four preprocessed echoes with consistent shapes/volume counts, valid echo
times, aligned fMRIPrep confounds, and events-file presence. It does not replace
the previous behavioral validation. Missing prerequisites stop the batch.

1. Process only the five subjects' ses-02 runs using existing production
   TEDANA settings. Skip complete outputs. Partial outputs are left untouched
   and reported for review, with no automatic deletion or overwrite.
2. Check exactly 20 acquired TEDANA runs. Generate only missing nuisance TSVs;
   recompute and compare existing TSVs, leaving their contents and mtimes intact.
   Verify finite matrix values, row counts against fMRIPrep and TEDANA images,
   and values against current fMRIPrep/mixing/classification inputs. This adds
   no residualization or scientific-model changes.
3. Back up current `run_qc.tsv` and `thresholds.tsv` privately, rebuild and
   check canonical QC within **task and session**, then rebuild/check
   descriptive scanner-era QC. Only these derived reports are overwritten.
4. Build/check a new private **baseline-only** Social Doors/UGR handoff,
   preserving existing decisions and holds. Ses-02 data are not added to the
   baseline paper cohort; QC flags are not exclusion decisions.

Each stage must pass before the next begins. The final success line is
`ALL STAGES PASSED`, and the outer run record must have command exit 0.
Successful TEDANA alone is not the complete closeout. Private outputs live
under the printed `work/wave2-tedana-...` directory, which must not be committed.
The run record and intended canonical/scanner-era QC outputs may be shared
after review. No message is sent to Jacob; exact paper-cohort reconciliation
still requires his cohort list.

## Individual Script Options

`run_tedana.sh`, `tedana.sh`, and `check_tedana.sh` accept `--session 01|02`;
omitting it retains the previous both-session scope. The checker optionally
requires `--expected-runs N` and rejects an empty selection.

`genTedanaConfounds.py` accepts the same session filter, `--expected-runs N`,
`--preserve-existing` (verify existing/create missing), and `--check`
(read-only verification). Existing mismatched matrices fail rather than being
silently accepted or overwritten. Legacy invocation without these options
retains the existing overwrite behavior. New files receive ordinary umask
permissions instead of tempfile's forced-private mode.
