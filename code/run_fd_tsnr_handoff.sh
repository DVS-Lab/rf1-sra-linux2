#!/usr/bin/env bash
# Build a separate, verified replacement; never launch MRIQC, FEAT or TEDANA.
set -euo pipefail
umask 0000
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PROJECT="$PWD"
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
PREVIOUS="$PROJECT/work/coverage95-handoff-20261021-204525"
STAMP="coverage95-fd-tsnr-handoff-$(date +%Y%m%d-%H%M%S)"
HANDOFF="$PROJECT/work/$STAMP"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

[[ -x "$AUDIT_PYTHON" ]] || { echo "Missing audit Python: $AUDIT_PYTHON"; exit 1; }
[[ -f "$PREVIOUS/provenance.json" ]] || { echo "Missing original handoff: $PREVIOUS"; exit 1; }
# Optional cohort arguments are forwarded verbatim, never guessed from filenames.
STATUS=0
bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/handoff_fd_tsnr.py build \
    --project "$PROJECT" --previous "$PREVIOUS" --output "$HANDOFF" "$@" \
  --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/handoff_fd_tsnr.py check \
    --project "$PROJECT" --output "$HANDOFF" || STATUS=$?

python3 code/publish_run_logs.py --project "$PROJECT"
printf '\nBuild/check exit: %s\nHANDOFF=%s\n' "$STATUS" "$HANDOFF"
if [[ "$STATUS" -eq 0 ]]; then
  printf '\n=== Validated unique-participant counts ===\n'
  cat "$HANDOFF/counts.tsv"
  printf '\n=== Replacement input tables ===\n'
  printf '%s\n' "$HANDOFF/socialdoors/selected_inputs.tsv" \
    "$HANDOFF/ugr/selected_inputs.tsv" "$HANDOFF/doors/selected_inputs.tsv"
  printf '\nRun reasons: %s/run_decisions.tsv\nSelection changes: %s/selection_changes.tsv\n' "$HANDOFF" "$HANDOFF"
  echo "Paper Ns require the approved survey/linkage cohort intersection; no L3 analysis was run."
fi
exit "$STATUS"
