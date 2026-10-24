#!/usr/bin/env bash
# Use the extracted fixed tool bundle without changing the production checkout.
set -euo pipefail
umask 0000

TOOLS=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT=${PROJECT_ROOT:-/ZPOOL/data/projects/rf1-sra-linux2}
PY=${AUDIT_PYTHON:-/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python}
REPAIR_10964=${REPAIR_10964:-$PROJECT/work/reviewed-source-repairs-v3}
REPAIR_11935=${REPAIR_11935:-$PROJECT/work/11935-final-repair-v1}
export PYTHONDONTWRITEBYTECODE=1

case "${1:-}" in
  check-10964)
    DEST="$REPAIR_10964/sub-10964-project"
    "$PY" "$TOOLS/upgrade_repair_geometry_check.py" \
      --project-root "$PROJECT" --workspace "$DEST" --apply
    "$PY" "$DEST/code/run_reviewed_source_repairs.py" check \
      --project-root "$PROJECT" --subject 10964 --private-dir "$REPAIR_10964"
    ;;
  finish-11935)
    DEST="$REPAIR_11935/sub-11935-project"
    RUNNER="$TOOLS/complete_11935_repair.py"
    if [[ -f "$DEST/repair.json" ]]; then
      "$PY" "$TOOLS/upgrade_repair_geometry_check.py" \
        --project-root "$PROJECT" --workspace "$DEST" --apply
      RUNNER="$DEST/code/complete_11935_repair.py"
    fi
    if [[ ! -f "$DEST/11935-ready.json" ]]; then
      "$PY" "$RUNNER" build --project-root "$PROJECT" \
        --work-dir "$REPAIR_11935" --jobs 8
    fi
    "$PY" "$RUNNER" check --project-root "$PROJECT" \
      --work-dir "$REPAIR_11935" --jobs 8
    ;;
  *)
    echo "Usage: bash $0 check-10964|finish-11935" >&2
    exit 2
    ;;
esac
