#!/usr/bin/env bash
set -euo pipefail
umask 0000
cd "$(dirname "${BASH_SOURCE[0]}")/.."
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
PREVIOUS="$PWD/work/coverage95-fd-tsnr-handoff-20261027-141630"
HANDOFF="$PWD/work/paper-handoff-fd-tsnr-paired-v1"
STAMP="paired-paper-handoff-$(date +%Y%m%d-%H%M%S)"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
STATUS=0
if [[ -e "$HANDOFF" ]]; then
  bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/pair_paper_handoff.py check \
      --output "$HANDOFF" || STATUS=$?
else
  bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
    env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/pair_paper_handoff.py build \
      --previous "$PREVIOUS" --output "$HANDOFF" \
    --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/pair_paper_handoff.py check \
      --output "$HANDOFF" || STATUS=$?
fi
python3 code/publish_run_logs.py --project "$PWD"
printf '\nBuild/check exit: %s\nHANDOFF=%s\n' "$STATUS" "$HANDOFF"
if [[ "$STATUS" -eq 0 ]]; then
  cat "$HANDOFF/counts.tsv"
  printf '\nJacob: %s/README.md\nMatched pairs: %s/paired_socialdoors/selected_pairs.tsv\nUGR: %s/ugr/selected_inputs.tsv\n' \
    "$HANDOFF" "$HANDOFF" "$HANDOFF"
fi
exit "$STATUS"
