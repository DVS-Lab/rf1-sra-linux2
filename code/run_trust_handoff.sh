#!/usr/bin/env bash
# Behavior-only staging; no imaging conversion or scientific fits.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
stage="${1:-}"
case "$stage" in validation|cohort) ;; *) echo 'Usage: bash code/run_trust_handoff.sh validation|cohort [--check-only]' >&2; exit 2;; esac
mode="${2:-}"
if [[ -n "$mode" && ( "$mode" != --check-only || "$stage" != validation ) ]]; then
  echo '--check-only is supported only for the validation stage.' >&2
  exit 2
fi
stamp="$(date -u +%Y%m%dT%H%M%SZ)-${stage}${mode}"
record="qc/trust_analysis/run_logs/$stamp"
mkdir -p "$record"
# Console includes conversion diagnostics but never copies private source contents.
exec > >(tee "$record/console.txt") 2>&1
finish() {
  result=$?
  trap - EXIT
  python3 - "$record/status.json" "$result" "$stage" <<'PY'
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps(dict(exit_code=int(sys.argv[2]),stage=sys.argv[3],
    finished_at=datetime.now(timezone.utc).isoformat(),git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()),indent=2)+'\n')
PY
  echo "Stage $stage exit=$result. Preserve $record when committing QC."
  exit "$result"
}
trap finish EXIT
python3 -c 'import sys; assert sys.version_info >= (3,11), "Activate the Linux2 Python environment first"'
if [[ -n "$(git status --porcelain --untracked-files=normal -- code tests Makefile requirements-dev.txt)" ]]; then
  echo 'Code checkout has local changes; reconcile them before production conversion.' >&2
  exit 1
fi
# QC/log output may be pending from the validation stage; never auto-stash it.
git rev-parse HEAD
make test PYTHON="$(command -v python3)"
work="${TRUST_HANDOFF_WORK:-$root/work/trust_schema}"
if [[ "$mode" == --check-only ]]; then
  # Reuse the original evidence; no snapshot creation or BIDS conversion.
  python3 code/trust_analysis_handoff.py check --scope validation --work "$work"
  echo 'Validation check complete; existing converted BIDS and original snapshot preserved.'
  exit 0
fi
if [[ ! -f "$work/${stage}.json" ]]; then
  python3 code/trust_analysis_handoff.py snapshot --scope "$stage" --work "$work"
else
  echo "Reusing original $stage snapshot in $work (never overwritten)."
fi
if [[ "$stage" == cohort ]]; then
  # Bind exclusions and valid runs to live source hashes before writing anything.
  python3 code/trust_analysis_handoff.py plan --scope cohort --work "$work"
  for run in 1 2; do
    if [[ -s "$work/cohort_run${run}_subjects.txt" ]]; then
      bash code/run_convert_behavior.sh --sublist "$work/cohort_run${run}_subjects.txt" --run "$run" --sessions 01 --tasks trust --jobs "${TRUST_CONVERSION_JOBS:-12}" --dry-run --overwrite
    fi
  done
  python3 code/trust_analysis_handoff.py plan --scope cohort --work "$work"
  for run in 1 2; do
    if [[ -s "$work/cohort_run${run}_subjects.txt" ]]; then
      bash code/run_convert_behavior.sh --sublist "$work/cohort_run${run}_subjects.txt" --run "$run" --sessions 01 --tasks trust --jobs "${TRUST_CONVERSION_JOBS:-12}" --overwrite
    fi
  done
else
  bash code/run_convert_behavior.sh --sublist "$work/${stage}_subjects.txt" --sessions 01 --tasks trust --jobs 4 --dry-run --overwrite
  bash code/run_convert_behavior.sh --sublist "$work/${stage}_subjects.txt" --sessions 01 --tasks trust --jobs 4 --overwrite
fi
python3 code/trust_analysis_handoff.py check --scope "$stage" --work "$work"
if [[ "$stage" == cohort ]]; then
  python3 code/build_events_qc.py build --dry-run
  python3 code/build_events_qc.py build --overwrite
  python3 code/build_events_qc.py check
  python3 code/trust_analysis_handoff.py export --work "$work"
else
  echo 'Validation complete. Review this log before running the cohort stage.'
fi
