#!/usr/bin/env bash
# Refresh descriptive QC, then measure (never smooth) all active task/session runs.
set -euo pipefail
umask 0000
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUTPUT="$ROOT/work/cohort-smoothness-v1"
JOBS=8
while (($#)); do
  case "$1" in
    --output) OUTPUT="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    *) echo "Usage: bash code/refresh_qc_smoothness.sh [--output DIR] [--jobs N]" >&2; exit 2 ;;
  esac
done
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || { echo 'jobs must be positive' >&2; exit 2; }
PYTHON="${AUDIT_PYTHON:-/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python}"
AFNI_BIN="${AFNI_BIN_DIR:-/ZPOOL/data/tools/anaconda/tug87422/envs/sharedreward-phase0/afni-bin}"
export PATH="$(dirname "$PYTHON"):$AFNI_BIN:$PATH"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$PYTHON" -c 'import nibabel, numpy, pandas, scipy, matplotlib, openpyxl'
for tool in 3dFWHMx afni flock; do command -v "$tool" >/dev/null; done
[[ -f /ZPOOL/data/projects/rf1-sra-sharedreward/code/measure_smoothness.sh ]]
OUTPUT="$("$PYTHON" - "$ROOT" "$OUTPUT" <<'PY'
from pathlib import Path
import sys
root, output = map(lambda s: Path(s).resolve(), sys.argv[1:])
if root / 'work' not in output.parents:
    raise SystemExit('Output must be a dedicated directory inside project/work')
print(output)
PY
)"
mkdir -p "$OUTPUT"
exec 9>work/qc-smoothness-refresh.lock
flock -n 9 || { echo 'QC/smoothness refresh already active; nothing started' >&2; exit 1; }
if [[ ! -f "$OUTPUT/plan.json" ]]; then
  if [[ ! -d "$OUTPUT/qc-before" ]]; then
    [[ ! -e "$OUTPUT/qc-before.partial" ]] || {
      echo 'Incomplete QC backup exists; inspect it before retrying. No QC changed.' >&2
      exit 1
    }
    cp -a qc "$OUTPUT/qc-before.partial"
    mv "$OUTPUT/qc-before.partial" "$OUTPUT/qc-before"
  fi
  echo 'Refreshing canonical QC with unchanged task/session policy; no eligibility decisions'
  "$PYTHON" code/build_run_qc.py build --overwrite
  "$PYTHON" code/build_run_qc.py check
  "$PYTHON" code/build_scanner_era_qc.py build --overwrite
  "$PYTHON" code/build_scanner_era_qc.py check
  "$PYTHON" code/measure_cohort_smoothness.py plan --output "$OUTPUT"
else
  echo 'Existing frozen measurement plan: preserving QC snapshot and completed measurements'
fi
run_status=0
"$PYTHON" code/measure_cohort_smoothness.py run --output "$OUTPUT" --jobs "$JOBS" --threads 1 || run_status=$?
check_status=0
"$PYTHON" code/measure_cohort_smoothness.py check --output "$OUTPUT" || check_status=$?
echo "Measurement exit=$run_status; validation exit=$check_status"
echo "Full tables and figures: $OUTPUT"
echo 'No smoothing, task-model rebuild, eligibility change, or cohort TEDANA restart performed.'
((run_status == 0 && check_status == 0))
