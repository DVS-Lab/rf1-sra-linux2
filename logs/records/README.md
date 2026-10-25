# Run Records

This directory is intentionally tracked. Use `code/run_logged.sh` to write a
small Markdown record for each logged pipeline run. The full raw logs remain
local under ignored `logs/runs/`.

Publish completed records with `python3 code/publish_run_logs.py --project "$PWD"`
from the project root. Published records can remain locally untracked until the
checkout is synchronized. After processing stops, follow the
[Git code/log workflow](../../docs/git-code-and-log-workflow.md); do not delete
records, remove locks, or create competing log-only commits on an older main.
