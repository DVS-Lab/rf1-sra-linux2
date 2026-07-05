# Validation History

This note preserves historical Linux2 validation names without making them
production defaults.

The production checkout is:

```bash
/ZPOOL/data/projects/rf1-sra-linux2
```

Older logs, run records, or notes may mention validation checkouts such as:

```bash
/ZPOOL/data/projects/rf1-sra-linux2-heudiconv14-test
/ZPOOL/data/projects/rf1-sra-linux2-jacob
```

Those paths were useful for isolated validation because the wrappers derive
`PROJECT_ROOT` from the checkout that is running them. They should not be used
as the default upstream path for downstream DWI processing now that production
documentation points at `/ZPOOL/data/projects/rf1-sra-linux2`.

Keep future validation subject lists under `logs/validation/` or another
review-only location. Do not replace `code/sublist-new.txt` with a tiny
validation list unless the operator intentionally wants that list to become the
current production batch.
