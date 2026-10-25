#!/usr/bin/env bash
# Isolated evaluation only. No production promotion, QC refresh, or exclusions.
set -euo pipefail
umask 0000
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="/ZPOOL/data/tools/anaconda/tug87422/envs/sharedreward-phase0/afni-bin:$PATH"
export PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
PYTHON="${AUDIT_PYTHON:-/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python}"
OUTPUT="$PWD/derivatives/smoothness-evaluation-6mm-v1"
COMMAND="${1:-}"
[[ $# -gt 0 ]] && shift
if [[ "$COMMAND" != run && $# -ne 0 ]]; then
  echo "ERROR: $COMMAND takes no extra arguments in this fixed-directory launcher" >&2
  exit 2
fi
case "$COMMAND" in
  plan|check)
    "$PYTHON" code/evaluate_smoothness_6mm.py "$COMMAND" "$@"
    ;;
  run)
    options=("$@")
    while (( $# )); do
      [[ ( "$1" == --jobs || "$1" == --threads ) && $# -ge 2 && "$2" =~ ^[1-9][0-9]*$ ]] || {
        echo "ERROR: run accepts only --jobs N and --threads N" >&2; exit 2;
      }
      shift 2
    done
    run_status=0; check_status=0
    "$PYTHON" code/evaluate_smoothness_6mm.py run "${options[@]}" || run_status=$?
    "$PYTHON" code/evaluate_smoothness_6mm.py check || check_status=$?
    echo "Processing exit: $run_status; validation/target-review exit: $check_status"
    (( run_status == 0 && check_status == 0 ))
    ;;
  export)
    # Only aggregate reports/plots, never NIfTI images or raw participant metadata.
    "$PYTHON" - "$OUTPUT" <<'PY'
import json
import fcntl
import shutil
import sys
from pathlib import Path
source = Path(sys.argv[1])
lock = (source / ".lock").open("a")
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
state = json.loads((source / "validation.json").read_text())
destination = Path("qc/smoothness_evaluation_6mm")
destination.mkdir(parents=True, exist_ok=True)
for name in ("report.md", "upper_tail.md", "upper_tail.tsv", "paired_summary.tsv", "validation.json"):
    shutil.copyfile(source / name, destination / name)
figures = destination / "figures"
figures.mkdir(exist_ok=True)
for image in (source / "figures").glob("*.png"):
    shutil.copyfile(image, figures / image.name)
print(f"Exported evaluation reports to {destination}; validation: {state}")
PY
    ;;
  *) echo "Usage: bash code/run_smoothness_6mm.sh {plan|run [--jobs N --threads N]|check|export}" >&2; exit 2 ;;
esac
