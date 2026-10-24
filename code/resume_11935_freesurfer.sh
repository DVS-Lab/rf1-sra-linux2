#!/usr/bin/env bash
set -euo pipefail
umask 0000
TOOLS=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT=${PROJECT_ROOT:-/ZPOOL/data/projects/rf1-sra-linux2}
PY=${AUDIT_PYTHON:-/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python}
WORK=${REPAIR_11935:-$PROJECT/work/11935-final-repair-v1}
DEST="$WORK/sub-11935-project"
export PYTHONDONTWRITEBYTECODE=1
"$PY" "$TOOLS/upgrade_repair_geometry_check.py" --freesurfer \
  --project-root "$PROJECT" --workspace "$DEST" --apply
if [[ ! -f "$DEST/11935-ready.json" ]]; then
  "$PY" "$DEST/code/complete_11935_repair.py" build \
    --project-root "$PROJECT" --work-dir "$WORK" --jobs 8
fi
"$PY" "$DEST/code/complete_11935_repair.py" check \
  --project-root "$PROJECT" --work-dir "$WORK" --jobs 8
