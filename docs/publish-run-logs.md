# Publish Linux2 Logs Without Updating Frozen Code

## Why Normal Pushes Keep Failing

Linux2 deliberately keeps an older checkout while frozen repairs depend on
its code. Meanwhile code fixes advance GitHub main. A local log commit on that
older history cannot fast-forward remote main. This is expected Git behavior,
not lost logs or a permissions problem. Do not force-push, pull, reset, rebase,
or create another branch merely to share routine run records.

`publish_run_logs.py` is the standard log-upload path while the checkout is
frozen. It publishes new timestamped `.md` and `.txt` files directly under
`logs/records/`, whether locally committed or untracked. It builds a logs-only
commit on the current remote main using a temporary Git index, then makes a
normal fast-forward push. Concurrent remote updates are retried up to three
times. Existing identical records are skipped. Different contents under the
same name or local edits to historical records require explicit review.

The helper does not publish code changes, delete records, copy work/ data,
advance the local branch, or alter the real Git index or any working file.
It preserves `umask 0000`. A dry run fetches remote state but makes no commit
or push. Temporary refs/indexes are removed when it exits.

## One-Time Installation

Use the published commit below. Fetch/archive does not update tracked code.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
git fetch origin
LOG_TOOL_REF=REPLACE_WITH_PUBLISHED_COMMIT
mkdir -p work/log-upload-tools
git archive "$LOG_TOOL_REF" code/publish_run_logs.py |
  tar -x -C work/log-upload-tools
```

## After Each Finished Run

Use this instead of `git add .`, `git commit`, and `git push` for logs:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
python3 work/log-upload-tools/code/publish_run_logs.py --project "$PWD"
```

Add `--dry-run` to preview. `PUBLISHED ...` or `ALREADY PUBLISHED ...` confirms
the upload. A failed upload retains every local log; retry the same command.
If a server rejects publication for permissions or policy reasons,
the error is reported rather than bypassed. Normal Git author identity and
remote authentication are used. Review records before sharing them; do not
place private raw headers in `logs/records/`.

`git status` can still show untracked logs and an older local main afterward.
That is intentional: publication does not rewrite the checkout. Repeating
the helper is safe and does not create duplicate commits. Code synchronization
is a separate action after frozen jobs/receipts allow it; this helper does not
authorize updating that checkout.

## Current Recovery

The user's `f9bb24c5` commit contains the October 24 FreeSurfer-resume and
DICOM-pixel-check records. Once the helper is installed it can publish those
two records directly, even though that commit is on older main. If the one-time
`logs-20261024-f9bb24c5` recovery branch has already been pushed/merged, the
helper recognizes identical records and does not duplicate them. No force push
or branch deletion is required.
