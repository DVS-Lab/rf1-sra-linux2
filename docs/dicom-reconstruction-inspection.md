# Read-only DICOM reconstruction comparison

The August scanner-era audit deliberately excluded all private DICOM tags. It
therefore cannot establish that Siemens/CMRR reconstruction settings were equal.
The new inspector retains non-pixel headers, reads nested enhanced-MR fields,
decodes Siemens CSA image/series headers with NiBabel, and parses available
ASCCONV blocks with NiBabel's parser. It never executes protocol content.

This is an evidence collection step, not a correction, eligibility decision,
new exclusion, or proof that XA60 caused the smoothness differences.

## Sampling and evidence limits

- Select up to three distinct participants per task/session/run/era from live
  BIDS echo-1 magnitude sidecars, at evenly spaced subject-ID ranks. No QC or
  smoothness values influence selection. Small strata use everyone available.
- Default eras: E11, XA30, XA60; sessions: 01 and 02. Comparisons never pool
  sessions. `selection-private.json` records both population and selected counts.
- Locate the same subject/session source folder, including session-2 supplemental
  folders, with no fallback from session 2 to session 1. Inspect up to 32 headers
  in each candidate series directory, stopping after an echo-1 magnitude match.
- Match series number, software era, description when present, echo time, image
  component, and BIDS study/series UIDs when present. Reject multiple distinct
  candidate series. A unique metadata match without a BIDS series UID is explicitly
  `metadata_candidate_only`, NOT an exact conversion-provenance link.
- Source files are not converted or modified. Only one selected instance per
  sample is retained as a non-pixel JSON header, not a whole series. Enhanced-MR
  nested fields in that instance are traversed. Other echoes/volumes may differ.
- Preserve complete non-pixel DICOM JSON and private opaque payloads in compressed
  JSON; decoded field comparisons contain public scientific fields, private
  scalar fields, CSA, ASCCONV and the original BIDS sidecar values.
- Comparisons preserve original units/types; they do not equate BIDS seconds
  with DICOM milliseconds or interpret vendor bit fields. Different observed
  value sets can reflect normal within-era variation, not an era-wide switch.
- Binary payloads not decoded as CSA/ASCCONV remain opaque with byte counts and
  hashes. Compressed/proprietary protocol formats and PhoenixZIP report objects
  are NOT decoded by this tool. Missing/undecodable settings remain UNKNOWN.
  A scanner-exported protocol may still be necessary.
- `CHECK PASSED` means selected headers were collected, not that all private
  fields were decoded, mapping was UID-exact, or protocols were equivalent.

## Linux2 launch without disturbing active repairs

After this code has been published, fetch and extract this single standalone
script into ignored `work/`. Do NOT pull, switch branches, or change tracked code
while a repair runner is checking a frozen code inventory. The existing logging
wrapper is used unchanged. This launches one header reader, not imaging jobs.

```bash
(
set -euo pipefail
umask 0000
cd /ZPOOL/data/projects/rf1-sra-linux2
git fetch origin main
REV=$(git rev-parse origin/main)
STAMP=dicom-reconstruction-$(date +%Y%m%d-%H%M%S)
TOOL_DIR="$PWD/work/${STAMP}-tool"
REVIEW_DIR="$PWD/work/${STAMP}"
mkdir -p "$TOOL_DIR" logs/runs
git show "$REV:code/inspect_dicom_reconstruction.py" \
  > "$TOOL_DIR/inspect_dicom_reconstruction.py"
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
"$AUDIT_PYTHON" -c 'import pydicom, nibabel; from nibabel.nicom import csareader, ascconv; print("Header parsers available")'
nohup setsid -f -w bash code/run_logged.sh \
  --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" \
    "$TOOL_DIR/inspect_dicom_reconstruction.py" \
    --project "$PWD" --private-dir "$REVIEW_DIR" \
    --sessions 01 02 --eras E11 XA30 XA60 --per-stratum 3 \
  > "logs/runs/${STAMP}.nohup.out" 2>&1 &
printf 'Tool revision: %s\nReview directory: %s\nLog: logs/runs/%s.nohup.out\n' \
  "$REV" "$REVIEW_DIR" "$STAMP"
)
```

Do not install dependencies into or alter the running TEDANA environment if the
preflight fails. Use a separate environment in that case. If a sample cannot be
mapped or decoded enough to read the header, its traceback stays in its
`sample-NNN/error-private.txt`, and collection continues for other samples.
Existing evidence directories are never overwritten; repeat into a new one.

## Review and sharing

`umask 0000` is applied explicitly. Directories/files use normal lab-shared
permissions (subject to inherited ACLs). "Private" means not published in Git;
it does not mean owner-only filesystem permissions.

The only Git-safe artifacts are the aggregate run record and `summary.md`.
The collector verifies that its output location is Git-ignored before writing.
Do not force-add the evidence package: DICOM headers can contain dates, patient
fields, UIDs, identifiers and private text, even when our task records do not.

For review, transfer the package privately to the workstation's Downloads:

- `reconstruction-private.tsv`: targeted reconstruction/filter/coil field comparison;
- `comparison-private.tsv`: all extracted fields, separated by task/session/run;
- `inventory-private.json`: exact source/BIDS paths, linkage status and fields;
- `sample-NNN/header-private.json.gz`: complete retained non-pixel DICOM header;
- `sample-NNN/decoded-private.json`: parsed protocols, decoder status and opaque inventory;
- `provenance.json`: script hash, arguments, parser version, output checksums.

The tracked run record contains counts/status only. A private copy of the
comparison tables is needed to interpret the actual new parameter values.

NiBabel parser reference: https://nipy.org/nibabel/reference/nibabel.nicom.html
