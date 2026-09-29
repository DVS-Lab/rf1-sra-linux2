# Shared Reward scoped local validation, 2026-09-29

Scope: technical checks independent of the three Shared Reward source-validity
closeouts. No BIDS, source, eligibility, model or QC-policy changes. The separate
RF1 backlogs retain their status. Demographic/preflight acceptance is complete
per `20260927-131417_participants-trust-preflight-20260927-131417.md`.

## Source-link tooling

`code/review_sharedreward_inventory.py` consumes the existing September 16
private inventory rather than rereading raw DICOMs. Live BIDS sidecar drift,
missing inputs, conflicting metadata, duplicated UID assignments and ambiguous
matches remain explicit. Unique metadata candidates are never exact UID links
or participant-identity approval. Only a whitelisted redacted report is printed.

Local test command using the installed FSL Python:

```bash
python -B -m unittest discover -s tests -p 'test_sharedreward*.py'
```

Result: **14 tests passed**, including the original real-DICOM/inventory tests
and six saved-inventory review tests. An earlier base-Python invocation passed
12 and skipped two imaging-dependent tests; the FSL-Python rerun had no skips.

The private inventory and live Linux2 BIDS images are not in this local clone.
No live source-series mapping is claimed. The documented follow-up must run on
Linux2 using `work/sharedreward-source-validity-20260916-000438/inventory.json`.
This is an engineering continuation, not a request for repeated lab review.

## Downstream contract tests

Read-only test runs against local `sharedreward-aging` commit `79ee586`:

| Test module | Tests | Final result |
| --- | ---: | --- |
| `test_fulltrial_candidate.py` | 1 | passed |
| `test_pooled_fsf.py` | 3 | passed |
| `test_l1_evs.py` | 2 | passed |
| `test_l1_runner.py` | 1 | passed under FSL Python, including real-header check |
| `test_l2_runner.py` | 2 | passed |

The L1 runner first errored because base Python lacked nibabel; it passed under
the existing FSL Python, without a code change or dependency installation.
The downstream checkout remained clean. Nine passing tests establish local
contract behavior, not production Linux2 output completeness, final cohort
approval, or scientific PPI sign-off. No production model was launched.

## 10668 chronology check

Private source history still shows the two run-1-design attempts in acquisition
commit `8c3b66ea6`, then a later split into run-1/run-2 names in `3f530e1e8`.
Those later filenames add no independent synchronization evidence. Reuse the
completed acquisition inventory before requesting only the remaining narrow
chronology fact. Do not revive the historical blanket task-exclusion judgment.
