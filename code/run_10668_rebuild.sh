#!/usr/bin/env bash
set -euo pipefail

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${scriptdir}/pipeline_common.sh"
rf1_load_config
cd "$scriptdir"
python="${REPAIR_PYTHON:-${TOOLS_ROOT}/anaconda/tug87422/envs/tedana-26.0.3/bin/python}"
inventory="${REPAIR_10668_INVENTORY:-${PROJECT_ROOT}/work/sharedreward-source-validity-20260916-000438/inventory.json}"
args=(--project-root "$PROJECT_ROOT" --inventory "$inventory" --behavior-root "$BEHAVIOR_ROOT"
      --exclusions-root "$SOURCEDATA_EXCLUSIONS_ROOT")

if [[ "$#" == 0 || ( "$#" == 1 && "$1" == "--dry-run" ) ]]; then
  "$python" repair_10668.py repair "${args[@]}"
  echo "Plan after apply: BIDS check, WarpKit, IntendedFor, MRIQC, fMRIPrep, geometry, TEDANA, confounds, alignment."
  exit 0
fi
if [[ "$#" != 2 || "$1" != "--apply" || "$2" != "--confirm-idle" ]]; then
  echo "Usage: bash run_10668_rebuild.sh [--dry-run | --apply --confirm-idle]" >&2
  exit 2
fi

mkdir -p "${PROJECT_ROOT}/logs/locks" "${PROJECT_ROOT}/logs/runlists"
lock="${PROJECT_ROOT}/logs/locks/10668-rebuild.lock"
if ! mkdir "$lock"; then
  echo "Rebuild lock exists; verify no prior rebuild is active before removing it: $lock" >&2
  exit 1
fi
trap 'rmdir "$lock"' EXIT
sublist="${PROJECT_ROOT}/logs/runlists/10668-reviewed-rebuild.txt"
printf '10668\n' > "$sublist"

"$python" repair_10668.py repair "${args[@]}" --apply --confirm-idle
"$python" repair_10668.py check "${args[@]}"
bash check_bids.sh --sublist "$sublist"
bash run_warpkit.sh --sublist "$sublist" --jobs 4
bash check_warpkit.sh --sublist "$sublist"
"$python" addIntendedFor.py --sublist "$sublist"
for ses in 01 02; do
  if [[ -d "${PROJECT_ROOT}/bids/sub-10668/ses-${ses}" ]]; then
    bash mriqc.sh 10668 "$ses"
  fi
done
bash check_mriqc.sh --sublist "$sublist"
bash fmriprep.sh 10668
bash check_fmriprep.sh --sublist "$sublist"

geometry="${PROJECT_ROOT}/logs/geometry/post-10668-repair-$(date +%Y%m%d-%H%M%S)"
"$python" fmriprep_geometry.py audit --report-prefix "$geometry"
"$python" fmriprep_geometry.py verify --audit-json "${geometry}.json"
export TEDANA_CMD
bash run_tedana.sh --sublist "$sublist" --jobs 1
bash check_tedana.sh --sublist "$sublist"
"$python" genTedanaConfounds.py --sublist "$sublist"
"$python" repair_10668.py check-products "${args[@]}"
"$python" check_events.py --subject 10668 --session 01 --behavior-root "$BEHAVIOR_ROOT" --quiet-ok
echo "CHECK PASSED: 10668 rebuild complete. Refresh cohort QC/analysis manifests before downstream analysis."
