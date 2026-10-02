# Run Record: socdoors-behavior-local

- Timestamp: 20261001-195955
- Branch: main
- Commit: b11c2357
- Host: CLA19733
- User: tug87422
- Working directory: `/Users/tug87422/github/rf1-sra-linux2`
- Raw log: `/Users/tug87422/github/rf1-sra-linux2/logs/runs/20261001-195955_socdoors-behavior-local.log`
- Command exit: 0
- Check exit: none
- Summary: CHECK PASSED: requested evidence collected; missing-task explanations remain to be reviewed.

## Command

```bash
python3 -B code/audit_socdoors_sources.py --behavior-only --behavior-root /Users/tug87422/github/rf1-sra/stimuli --private-output work/socdoors-behavior-local-20261001
```

## Full Log

```text
RUN START: 20261001-195955
PROJECT_ROOT: /Users/tug87422/github/rf1-sra-linux2
GIT: main b11c2357
HOST: CLA19733
USER: tug87422
PWD: /Users/tug87422/github/rf1-sra-linux2
COMMAND: python3 -B code/audit_socdoors_sources.py --behavior-only --behavior-root /Users/tug87422/github/rf1-sra/stimuli --private-output work/socdoors-behavior-local-20261001

# Missing Doors follow-up: read-only evidence, not recovery approval

## Behavioral sources (not proof of corresponding MRI acquisition)
subject | session | task | source status | trials | missed | last event end (s)
---|---|---|---|---|---|---
11083 | 01 | doors | missing | - | - | -
11083 | 01 | socialdoors | missing | - | - | -
11083 | 02 | doors | available | 40 | 1 | 330.959
11083 | 02 | socialdoors | available | 40 | 3 | 333.091
11085 | 01 | doors | missing | - | - | -
11085 | 01 | socialdoors | missing | - | - | -
11085 | 02 | doors | missing | - | - | -
11085 | 02 | socialdoors | missing | - | - | -
11110 | 01 | doors | missing | - | - | -
11110 | 01 | socialdoors | missing | - | - | -
11110 | 02 | doors | missing | - | - | -
11110 | 02 | socialdoors | missing | - | - | -
11128 | 01 | doors | missing | - | - | -
11128 | 01 | socialdoors | missing | - | - | -
11128 | 02 | doors | missing | - | - | -
11128 | 02 | socialdoors | missing | - | - | -
11145 | 01 | doors | missing | - | - | -
11145 | 01 | socialdoors | missing | - | - | -
11145 | 02 | doors | missing | - | - | -
11145 | 02 | socialdoors | missing | - | - | -
11171 | 01 | doors | available | 40 | 1 | 330.217
11171 | 01 | socialdoors | available | 40 | 0 | 331.376
11171 | 02 | doors | missing | - | - | -
11171 | 02 | socialdoors | missing | - | - | -
11203 | 01 | doors | available | 1 | 1 | 5.190
11203 | 01 | socialdoors | available | 35 | 1 | 289.765
11203 | 02 | doors | missing | - | - | -
11203 | 02 | socialdoors | missing | - | - | -
11317 | 01 | doors | missing | - | - | -
11317 | 01 | socialdoors | missing | - | - | -
11317 | 02 | doors | missing | - | - | -
11317 | 02 | socialdoors | missing | - | - | -
11364 | 01 | doors | missing | - | - | -
11364 | 01 | socialdoors | missing | - | - | -
11364 | 02 | doors | missing | - | - | -
11364 | 02 | socialdoors | missing | - | - | -
11396 | 01 | doors | missing | - | - | -
11396 | 01 | socialdoors | missing | - | - | -
11396 | 02 | doors | missing | - | - | -
11396 | 02 | socialdoors | missing | - | - | -
11443 | 01 | doors | missing | - | - | -
11443 | 01 | socialdoors | missing | - | - | -
11443 | 02 | doors | missing | - | - | -
11443 | 02 | socialdoors | missing | - | - | -

BEHAVIOR-ONLY: no source DICOMs, saved series inventories, or session notes checked.

Exact metadata saved only in ignored work/. Do not commit that directory.
Session notes were not located/read by this utility. Behavioral completion does not prove MRI coverage.
No data, conversions, or exclusions changed.
Collection errors/missing required inputs: 0
CHECK PASSED: requested evidence collected; missing-task explanations remain to be reviewed.

COMMAND EXIT: 0
```
