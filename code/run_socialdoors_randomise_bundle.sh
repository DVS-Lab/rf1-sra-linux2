#!/usr/bin/env bash
set -euo pipefail
umask 0000
cd "$(dirname "${BASH_SOURCE[0]}")/.."
AUDIT_PYTHON=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
MODE=${1:-pool}
COHORT=()
case "$MODE" in
  pool) OUTPUT="$PWD/work/randomise-socialdoors-age55-pool-v1" ;;
  final)
    COHORT_FILE="$PWD/docs/paper-handoff/cohorts/katie-final.tsv"
    [[ -f "$COHORT_FILE" ]] || { echo "STOP: Jacob's ordered ID-only cohort is needed at $COHORT_FILE"; exit 1; }
    COHORT=(--cohort "$COHORT_FILE")
    OUTPUT="$PWD/work/randomise-katie-final-v1"
    ;;
  *) echo "Usage: bash code/run_socialdoors_randomise_bundle.sh [pool|final]"; exit 2 ;;
esac
[[ $# -le 1 ]] || { echo "Unexpected extra arguments"; exit 2; }
STAMP="socialdoors-randomise-${MODE}-$(date +%Y%m%d-%H%M%S)"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
STATUS=0
bash code/run_logged.sh --label "$STAMP" --include-full-log -- \
  env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/build_socialdoors_randomise.py build \
    --output "$OUTPUT" "${COHORT[@]}" \
  --check env PYTHONUNBUFFERED=1 "$AUDIT_PYTHON" code/build_socialdoors_randomise.py check \
    --output "$OUTPUT" || STATUS=$?
python3 code/publish_run_logs.py --project "$PWD"
printf '\nBundle/check exit: %s\nOUTPUT=%s\n' "$STATUS" "$OUTPUT"
exit "$STATUS"
