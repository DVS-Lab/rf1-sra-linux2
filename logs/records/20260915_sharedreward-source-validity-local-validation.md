# Shared Reward source-validity audit: local validation

Date: 2026-09-15. Environment: local macOS clone, **not Linux2 execution**.

Scope: add a read-only DICOM/behavior inventory for 10668 and 11913/11923,
record the conditional 10657 Shared Reward run decision, leave Trust and
imaging-QC exclusions unchanged. No BIDS, behavioral source, FEAT model,
generated cohort, or image was modified by this work.

## Validation

Command:

```text
/Users/tug87422/fsl/bin/python3 -m unittest discover -s tests -p test_sharedreward_sources.py -v
```

Result: **8 tests passed**, no skips, exit 0. Python 3.12.12, pydicom 3.0.1,
nibabel 5.3.2. Tests cover real synthetic DICOM header reading, a complete
synthetic DICOM/NIfTI/behavior inventory, byte-for-byte unchanged input files,
private 0700/0600 output, refusal to overwrite or emit private inventory under
tracked logs, public-output redaction, echo/duplicate handling, repeated
behavioral segments, and explicit rather than substituted acquisition timing.

The documented Linux2 shell block passed `bash -n`. `git diff --check` passed.
`git check-ignore work/sharedreward-source-validity-example/inventory.json`
confirmed the private output location is ignored. Existing pytest-based
regression suites were not rerun because pytest is unavailable in the local
runtimes; no production converter or processing worker was modified.

## Remaining execution

Linux2 must run the scoped audit against the actual mounted source/BIDS trees.
The planned container is the existing HeuDiConv 1.4.0 image; it was not executed
on this Mac. An inventory-complete exit is not source-identity approval. See
`docs/sharedreward-source-validity.md` for commands, limits and decision scope.
