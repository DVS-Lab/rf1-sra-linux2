# Baseline Participant Metadata

`code/participants.py` reconstructs `bids/participants.tsv` and its JSON
sidecar from the saved HeuDiConv session-01 sequence inventories. The script
uses Python's standard library; no image conversion, DICOM rescan, or Conda
package installation is required. This repairs the omission of dataset-level
participant metadata from the staged `prepdata.sh` installation.

The source is precisely
`bids/.heudiconv/SUBJECT/ses-01/info/dicominfo_ses-01.tsv`, using `patient_age`
and `patient_sex`. HeuDiConv 1.4.0 populates those fields from DICOM `PatientAge`
and `PatientSex` ([source](https://github.com/nipy/heudiconv/blob/v1.4.0/heudiconv/dicoms.py)).
This recovers the scanner-demographic product; it does not claim independent
REDCap verification or infer age from dates. Years are retained, months are
converted to years to two decimal places, and unsupported encodings stop for
review. The subject ID comes from the reviewed conversion directory, not a
potentially misentered DICOM patient identifier. `sex` is scanner-recorded sex,
not a claim about gender or how the information was obtained.

## Recovery on Linux2

Run from a clean, updated upstream checkout. The subshell stops immediately
if preview, installation, or verification fails, without closing your terminal.

```bash
(
  set -euo pipefail
  cd /ZPOOL/data/projects/rf1-sra-linux2
  git pull --ff-only
  umask 0000
  ELIGIBILITY=qc/trust_analysis/run_eligibility.tsv
  STAMP=participants-recovery-$(date +%Y%m%d-%H%M%S)

  bash code/run_logged.sh --label "${STAMP}-preview" --include-full-log -- \
    python3 code/participants.py build --eligibility "$ELIGIBILITY"

  bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
    python3 code/participants.py build --apply --eligibility "$ELIGIBILITY" \
    --check python3 code/participants.py check --eligibility "$ELIGIBILITY"
)
```

The installed table includes non-source-excluded BIDS subjects. The explicit
eligibility check additionally requires rows for every structurally eligible,
non-source-excluded Trust participant (343 in the September 27 export).
No QA/QC metric or response threshold affects this export. Existing authoritative
source-folder exclusions remain effective; no new exclusions are inferred.

Conflicting series values, invalid encodings, missing sequence inventories,
duplicate IDs, and contradictions with known existing demographic values fail
before installation. Missing values in actual source metadata remain `n/a` and
are counted, including separately for eligible Trust participants. A passed
coverage check does not mean every age/sex value is known. Missing values can
affect the downstream age-analysis sample and must be reviewed in the report.

## Downstream Acceptance

Use the explicit interpreter from the Trust repository's documented Linux2
environment. An unqualified `python3` in a base Conda shell may not have the
analysis package installed even when recovery succeeded.

```bash
cd /ZPOOL/data/projects/rf1-trust-socialvalue
bash ../rf1-sra-linux2/code/run_logged.sh \
  --label "participants-trust-preflight-$(date +%Y%m%d-%H%M%S)" \
  --include-full-log -- \
  env PYTHONPATH="$PWD/src" \
  "$PWD/.venv-linux2/bin/python" -m rf1_trust_socialvalue.full_sample preflight
```

This writes the preflight evidence into upstream `logs/records/`, without
freezing the cohort or launching models. After verification, the existing
`bash scripts/run_full_sample_gate.sh` resumes the scientific integration gate.
The export, missingness report and downstream preflight have now been verified;
the participant-metadata blocker is closed. Passing preflight does not establish
later scientific/model parity checks.

### Verified Recovery, 2026-09-27

The [Linux2 installation and check](../../logs/records/20260927-130749_participants-recovery-20260927-130745.md)
both exited 0: 352 exported rows, no unknown ages or sex values, and all 343
eligible Trust participants covered. The
[independent check report](20260927T170749Z-a28c78ee-check.json) records zero
issues. The exported TSV SHA-256 is
`10004009f83ae3ffd9977941e6c222ac8f1aabfd70f41968470cfaa70ef35ca4`.

The [first downstream preflight](../../logs/records/20260927-130812_participants-trust-preflight-20260927-130812.md)
used base Conda Python and failed to import `rf1_trust_socialvalue`; it never
reached demographic validation. The [13:14 retry](../../logs/records/20260927-131417_participants-trust-preflight-20260927-131417.md)
passed canonical input paths and demographics coverage (exit 0), using the
Trust interpreter with `PYTHONPATH` pointing to current source. Preserve the
earlier failed logs; no further reconstruction or preflight retry is needed.

Commit only `qc/participants/` reports and the relevant `logs/records/` Markdown
files. The TSV, sidecar, and backups stay in the ignored BIDS tree. Reports
contain source hashes, row counts, missingness, and sanitized issues; no age/sex
values, birth dates, acquisition dates, DICOM identifiers, or raw source rows.

## Future Conversions and Provenance

### October 15 coverage reconciliation

The September recovery established metadata completeness for the then-present
non-source-excluded BIDS cohort, not that every acquired RF1 participant had
reached BIDS. All 33 IDs reported missing by Jacob are also absent from the
September recovery's 352-subject provenance inventory. That observation alone
does not distinguish unprocessed imaging from intentional source exclusions or
participants without locally available scans. Do not treat this as a stale-copy
diagnosis, an age-based exclusion, or proof someone was never scanned.

`code/audit_participant_coverage.py` performs a read-only filesystem reconciliation
for those 33 plus IDs discovered in conventional production/excluded source
folders, BIDS, conversion inventories, the current participant table and active
fMRIPrep/MRIQC/TEDANA/WarpKit derivatives. It reads no DICOM headers or pixels.
Filename counts establish local file evidence, not image validity, task identity
or complete acquisition. Permission errors, unavailable roots and directory
symlinks stop the audit rather than silently becoming missing-data claims.
Unmatched source directory counts require private follow-up; XNAT, other hosts,
compressed archive contents and misregistered IDs are outside this audit.

Run on Linux2 (may take several minutes to enumerate the cohort):

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
git pull --ff-only
STAMP=participants-coverage-$(date +%Y%m%d-%H%M%S)
mkdir -p logs/runs
nohup setsid -f -w bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  python3 code/audit_participant_coverage.py --private-dir "work/$STAMP" \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
echo "$STAMP"
```

Only aggregate counts go into the shareable run record. `work/$STAMP/review.tsv`
and `inventory.json` hold per-ID evidence in a new mode-0700 directory; keep these
private, including source-exclusion membership. They contain no ages, dates,
diagnoses, or DICOM identifiers. Do not commit them or change the exclusion policy.

Interpretation/actions:

- `intentional_source_exclusion`: accounted for separately, not added back to the
  standard analysis/release participant table, even if residual BIDS exists.
- `bids_missing_participant_row`: repair metadata from saved baseline provenance
  after reviewing the reported source status; do not reconvert images blindly.
- `raw_present_conversion_review`: inspect the source series and establish usable
  imaging, then process if appropriate. Localizer-only files are not sufficient.
- `derivatives_without_bids_review` or `conversion_inventory_without_images`:
  investigate moved/deleted BIDS or alternate roots before any reprocessing.
- `source_folder_without_recognized_dicoms`: inspect download/archive/layout.
- `no_local_imaging_evidence`: search acquisition records/XNAT/backups or identity
  mappings. This is not a declaration that MRI was never acquired.
- Table duplicates, excluded rows in the table, or represented rows lacking
  baseline provenance require reconciliation rather than silent overwrite.

No live October 15 results are available yet. The local tests establish audit
behavior only; completeness for the 33 remains open pending the Linux2 report.
The standard table must cover the full non-source-excluded BIDS cohort; a separate
private reconciliation accounts for everyone else without inventing scanner ages
or reintroducing excluded participants. Research-demographic coverage is a
different scope from BIDS imaging membership.

`prepdata.sh` previews participant metadata before installing session output.
After installation it merges the participant and verifies the result. Session 02
uses saved session-01 demographics and never changes baseline age to follow-up
age. `check_bids.sh` now verifies metadata for its requested subjects.

Concurrent updates share a file lock. Existing unrelated participant rows and
extra columns are preserved; existing known values cannot be silently changed.
Before replacement, old TSV/JSON files are copied into a private
`bids/.participants-backups/` directory. Each file is installed atomically;
the sidecar's TSV digest makes an interruption between installations detectable.
Run the checker before downstream use. Generated metadata follows the caller's
umask, while backups are private.

`participants.json` records each baseline source hash, relative source path,
missing-series counts, and the exported table hash. The checker re-reads the
baseline sources, checks hashes and values, and checks required cohort coverage.
If an authoritative research-demographic correction is needed later, review
that change separately; this recovery tool deliberately refuses conflicting
values instead of choosing one silently.
