#!/usr/bin/env bash
# Read-only, all-age inventory in an isolated reporting release.
set -euo pipefail
umask 0000
PROJECT=${LIFESPAN_PROJECT:-/ZPOOL/data/projects/rf1-sra-linux2}
cd "$PROJECT"
RELEASE=$(git rev-parse FETCH_HEAD)
FROZEN="$PROJECT/work/lifespan-inventory-release-${RELEASE:0:12}"
mkdir -p "$PROJECT/work"
if [[ ! -e "$FROZEN" ]]; then
  TEMP=$(mktemp -d "$PROJECT/work/.lifespan-release-XXXXXX")
  git archive "$RELEASE" code/inventory_lifespan_measures.py | tar -x -C "$TEMP"
  mv "$TEMP" "$FROZEN"
fi
[[ -f "$FROZEN/code/inventory_lifespan_measures.py" && ! -L "$FROZEN" ]] || {
  echo "STOP: incomplete or symlinked reporting release; no analysis process changed."
  exit 1
}
git show "$RELEASE:code/inventory_lifespan_measures.py" | \
  cmp - "$FROZEN/code/inventory_lifespan_measures.py"
STAMP=lifespan-inventory-$(date +%Y%m%d-%H%M%S)
OUTPUT="$PROJECT/work/$STAMP"
publish_logs() {
  local status=$?
  trap - EXIT
  env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.url \
    GIT_CONFIG_VALUE_0=https://github.com/DVS-Lab/rf1-sra-linux2.git \
    python3 "$PROJECT/code/publish_run_logs.py" --project "$PROJECT" || {
    echo "LOG PUBLICATION FAILED; retry: python3 $PROJECT/code/publish_run_logs.py --project $PROJECT"
    [[ "$status" -ne 0 ]] || status=1
  }
  exit "$status"
}
trap publish_logs EXIT
bash "$PROJECT/code/run_logged.sh" --label "$STAMP" --include-full-log -- \
  python3 "$FROZEN/code/inventory_lifespan_measures.py" \
    --project "$PROJECT" --output "$OUTPUT" \
    --discover-root /ZPOOL/data/projects/rf1-sra \
    --discover-root /ZPOOL/data/projects/rf1-sra-socdoors \
    --discover-root /ZPOOL/data/projects/rf1-sra-environment-SD "$@"
