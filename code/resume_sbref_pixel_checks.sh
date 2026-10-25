#!/usr/bin/env bash
# Run from the production project root; this script lives in an extracted bundle.
set -euo pipefail
umask 0000
ROOT=/ZPOOL/data/projects/rf1-sra-linux2
PY=/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python
TOOLS=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
STAGED="$ROOT/work/11935-final-repair-v1/sub-11935-project"
cd "$ROOT"
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
case "${1:-}" in
  preview)
    "$PY" "$TOOLS/upgrade_11935_sbref.py" --project-root "$ROOT" --workspace "$STAGED"
    ;;
  repair)
    "$PY" "$TOOLS/upgrade_11935_sbref.py" --project-root "$ROOT" --workspace "$STAGED" --apply
    "$PY" "$STAGED/code/complete_11935_repair.py" build --project-root "$ROOT" \
      --work-dir "$ROOT/work/11935-final-repair-v1" --jobs 8
    "$PY" "$STAGED/code/complete_11935_repair.py" check --project-root "$ROOT" \
      --work-dir "$ROOT/work/11935-final-repair-v1" --jobs 8
    ;;
  pixels)
    OUT="$ROOT/work/dicom-bids-pixels-retry-$(date +%Y%m%d-%H%M%S)"
    "$PY" "$TOOLS/check_dicom_bids_pixels.py" --project "$ROOT" \
      --inventory "$ROOT/work/dicom-reconstruction-20261024-154055/inventory-private.json" \
      --retry-report "$ROOT/work/dicom-bids-pixels-20261024-201433/report-private.json" \
      --output "$OUT"
    ;;
  *) echo "Usage: bash $0 {preview|repair|pixels}" >&2; exit 2 ;;
esac
