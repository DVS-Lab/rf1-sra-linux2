# Shared Reward conversion-link follow-up, 2026-09-29

The sidecar-only Linux2 review at 01:00 completed with no changed sidecars or
incomplete inventory, but zero exact UID links. Shared Reward run-1 series
number 25 occurs in both source folders. This is a metadata ambiguity, not
proof of a participant swap. The three source-validity closeouts remain scoped
as documented in `docs/sharedreward-source-validity.md`.

The optional `--conversion-provenance` review now follows the effective saved
HeuDiConv edit-table output to the selected sequence's series UID and the
existing private inventory. It verifies populated filegroup membership/count
and available metadata consistency, and records three conversion-file hashes.
Literal records are parsed without executing the heuristic. Missing/conflicting
records are not replaced with filename guesses, current heuristic ordering,
an auto table, or a new DICOM scan. Recorded linkage is distinct from pixel
identity and correct historical participant registration.

Reference contract: HeuDiConv v1.4.0 `conversion_info` and `prep_conversion`
in [convert.py](https://github.com/nipy/heudiconv/blob/v1.4.0/heudiconv/convert.py),
and the `SeqInfo.series_uid` field in `utils.py` at that version.

Local verification using the installed FSL Python:

```bash
python -B -m unittest discover -s tests -p 'test_sharedreward*.py'
```

Result: **18 tests passed, no skips**. Added coverage includes duplicated
series numbers across participants, explicit run-order mapping, missing effective
edit tables, code-like input rejected without execution, sidecar UID mismatch,
file-count conflict, duplicate output assignments, redaction and read-only
operation. Earlier snapshot-drift and source-reuse protections remain tested.

No live Linux2 provenance mapping is claimed by these tests. No BIDS files,
behavioral assignments, cohort decisions, QA policy, or models were changed.
The next operator command is the existing short review with
`--conversion-provenance`; share only the redacted run record.
