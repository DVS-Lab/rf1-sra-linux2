#!/usr/bin/env bash
set -euo pipefail
umask 0000
cd "$(dirname "${BASH_SOURCE[0]}")/.."
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
PREVIOUS="$PWD/work/coverage95-fd-tsnr-handoff-20261027-141630"
OUTPUT="$PWD/work/socialdoors-paired-diagnostic-v1"
STAMP="socialdoors-paired-diagnostic-$(date +%Y%m%d-%H%M%S)"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export MPLBACKEND=Agg
STATUS=0
bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/diagnose_socialdoors_difference.py build \
    --previous "$PREVIOUS" --output "$OUTPUT" --jobs 8 \
  --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/diagnose_socialdoors_difference.py check \
    --output "$OUTPUT" || STATUS=$?
python3 code/publish_run_logs.py --project "$PWD"
printf '\nDiagnostic/check exit: %s\nREPORT=%s/README.md\nPLOTS=%s/*.png\n' "$STATUS" "$OUTPUT" "$OUTPUT"
exit "$STATUS"
