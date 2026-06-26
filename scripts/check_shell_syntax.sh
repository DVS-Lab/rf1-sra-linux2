#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"
cd "$repo_root"

while IFS= read -r script; do
  bash -n "$script"
done < <(git ls-files '*.sh')

if command -v shellcheck >/dev/null 2>&1; then
  shellcheck \
    code/pipeline_common.sh \
    code/run_prepdata.sh \
    code/prepdata-linux2.sh \
    code/run_warpkit.sh \
    code/warpkit.sh \
    code/run_fmriprep.sh \
    code/fmriprep.sh \
    code/run_tedana.sh \
    code/tedana.sh \
    code/run_mriqc.sh \
    code/mriqc.sh \
    code/check_fmriprep.sh \
    code/check_tedana.sh \
    code/check_mriqc.sh \
    code/submit_fmriprep.sh
else
  echo "ShellCheck not installed; skipped shellcheck lint."
fi
