# Git Code And Log Workflow

Use Git for code, tests, documentation and sanitized run records. Use SCP for
large/private review archives and images that must not enter Git. The temporary
SCP-delivered installer bundles were a workaround while Linux2's checkout was
frozen, not the intended long-term code-distribution workflow. The validated
installer and its regression tests now belong in this repository.

## While Processing

Do not update code being read by active processing or invalidate frozen code
receipts. Publish completed run records with:

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
python3 code/publish_run_logs.py --project "$PWD"
```

This appends records to remote main without changing local HEAD, tracked code,
index or working files. Thus logs can be published successfully while still
appearing untracked locally, and local main can fall behind origin/main.
That is intentional preservation, not a failed upload. Avoid `git add .` and
separate log-only local commits; they recreate divergent branch histories.

## After Processing Stops

The installer and cohort experiment have completed. Synchronize Linux2's main
with Git once no process relies on the old checkout. A plain fast-forward can
be blocked by the already-published untracked records. The standalone helper
verifies byte identity with incoming Git blobs, saves copies under ignored
`work/checkout-sync/`, moves only those identical records aside, and runs
`git merge --ff-only` against the pinned fetched commit. On merge failure it
restores missing records without overwriting anything. Backups are retained.

```bash
cd /ZPOOL/data/projects/rf1-sra-linux2
umask 0000
set -o pipefail
git fetch origin
git show origin/main:code/sync_published_checkout.py | \
  python3 - --project "$PWD" --apply --processing-stopped
git status --short --branch
```

The script runs directly from the fetched Git blob, so no SCP or initial pull
is needed. It refuses tracked edits, divergent commits, mismatched records,
symlinks and non-log collisions. It never force-pushes, resets, rebases or
cleans. `.11935-repair.lock` and `.reviewed-install.lock` are ignored runtime
files; leave them in place rather than unlinking coordination locks.

## Installation Closeout

`20261025-094314_reviewed-install-v3-20261025-094314` confirms command/check
exit 0: 972 replacement files verified, 902 original files/entries preserved,
10964 ses-02 four functional runs and 11935 ses-01 two functional runs installed.
Cohort TEDANA, baseline data, QC tables, demographics and settled exclusions
were unchanged. Nineteen retired downstream entries are listed for separate
rebuild review; they are not nineteen failed or missing imaging acquisitions.

Pending: canonical QC/task-manifest refreshes and only the eligible stale
task-level outputs identified by the installation receipt. The completed
cohort experiment is historical and must not be resumed against changed
production inputs. 11935 remains excluded from the current papers and the
10964 repair is session 02 only.
