#!/usr/bin/env bash
# Finish the five validated October 16 sessions, without changing eligibility.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
usage() { echo 'Usage: bash code/resume_wave2_tedana.sh [--dry-run]' >&2; }
dry_run=0
if (($#)); then
  [[ $# == 1 && "$1" == --dry-run ]] || { usage; exit 2; }
  dry_run=1
fi
export PATH="${AUDIT_BIN:-/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin}:$PATH"
export TEDANA_CMD="${TEDANA_CMD:-/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/tedana}"
export PYTHONUNBUFFERED=1
jobs="${TEDANA_JOBS:-4}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'TEDANA_JOBS must be positive' >&2; exit 2; }
mkdir -p work
exec 9>work/resume-wave2-tedana.lock
flock -n 9 || { echo 'Another wave2 resume is running; no work started.' >&2; exit 1; }
work="$(mktemp -d "$root/work/wave2-tedana-$(date +%Y%m%d-%H%M%S).XXXXXX")"
chmod 700 "$work"
printf '%s\n' 11083 11084 11110 11120 11193 > "$work/subjects.txt"
echo "Private verification directory: $work"

echo 'STAGE: preflight exactly 20 ses-02 runs (no ses-01 processing)'
python3 - "$root" "$work/subjects.txt" <<'PY'
import json
import os
from pathlib import Path
import sys
import nibabel as nib
import pandas as pd

root, sublist = map(Path, sys.argv[1:])
excluded = Path(os.environ.get('SOURCEDATA_EXCLUSIONS_ROOT', '/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions'))
if not excluded.is_dir():
    raise SystemExit('Required source-exclusion root unavailable')
count = 0
for sub in sublist.read_text().split():
    if (excluded / f'Smith-SRA-{sub}').exists():
        raise SystemExit('A requested subject is source-excluded; stop for private review')
    bids = root / 'bids' / f'sub-{sub}' / 'ses-02' / 'func'
    func = root / 'derivatives/fmriprep' / f'sub-{sub}' / 'ses-02' / 'func'
    expected = {f'sub-{sub}_ses-02_task-{task}_run-{run}'
                for task, run in [('doors', 1), ('socialdoors', 1), ('ugr', 1), ('ugr', 2)]}
    actual = {p.name.removesuffix('_echo-1_part-mag_bold.nii.gz')
              for p in bids.glob('*_echo-1_part-mag_bold.nii.gz')}
    if actual != expected:
        raise SystemExit(f'sub-{sub}: expected exactly four reviewed ses-02 runs; stop for review')
    for stem in sorted(expected):
        shapes = []
        for echo in range(1, 5):
            raw = nib.load(bids / f'{stem}_echo-{echo}_part-mag_bold.nii.gz')
            image = nib.load(func / f'{stem}_echo-{echo}_part-mag_desc-preproc_bold.nii.gz')
            if len(raw.shape) != 4 or len(image.shape) != 4 or raw.shape[3] != image.shape[3]:
                raise SystemExit(f'{stem}: BIDS/preprocessed volume count mismatch')
            shapes.append(image.shape)
            metadata = json.loads((bids / f'{stem}_echo-{echo}_part-mag_bold.json').read_text())
            if not isinstance(metadata.get('EchoTime'), (int, float)) or not metadata['EchoTime'] > 0:
                raise SystemExit(f'{stem}: missing/invalid EchoTime')
        if len(set(shapes)) != 1:
            raise SystemExit(f'{stem}: preprocessed echo shapes differ')
        confounds = pd.read_csv(func / f'{stem}_part-mag_desc-confounds_timeseries.tsv', sep='\t')
        if len(confounds) != shapes[0][3]:
            raise SystemExit(f'{stem}: fMRIPrep confound row mismatch')
        if not (bids / f'{stem}_events.tsv').is_file():
            raise SystemExit(f'{stem}: missing events')
        count += 1
print(f'PREFLIGHT PASSED: {count} acquired runs with four echoes and aligned fMRIPrep confounds')
PY

args=(--sublist "$work/subjects.txt" --session 02)
if ((dry_run)); then
  bash code/run_tedana.sh "${args[@]}" --jobs "$jobs" --dry-run
  echo 'DRY RUN COMPLETE: no TEDANA/confound/QC/handoff products written.'
  exit 0
fi

echo 'STAGE: TEDANA (skip complete; stop on partial outputs; never overwrite)'
bash code/run_tedana.sh "${args[@]}" --jobs "$jobs"
bash code/check_tedana.sh "${args[@]}" --expected-runs 20
echo 'STAGE: confounds (verify existing; generate missing only)'
python3 code/genTedanaConfounds.py "${args[@]}" --expected-runs 20 --preserve-existing
python3 code/genTedanaConfounds.py "${args[@]}" --expected-runs 20 --check

echo 'STAGE: canonical QC, separately within each task/session'
cp -p qc/run_qc.tsv "$work/run_qc.before.tsv"
cp -p qc/thresholds.tsv "$work/thresholds.before.tsv"
python3 code/build_run_qc.py build --overwrite
python3 code/build_run_qc.py check
echo 'STAGE: descriptive scanner-era QC'
python3 code/build_scanner_era_qc.py build --overwrite
python3 code/build_scanner_era_qc.py check
echo 'STAGE: baseline paper handoff; settled holds retained, QC flags separate'
handoff=(python3 code/refresh_task_handoff.py build --private-dir "$work/handoff")
[[ ! -f qc/run_disposition.tsv ]] || handoff+=(--dispositions "$root/qc/run_disposition.tsv")
"${handoff[@]}"
python3 code/refresh_task_handoff.py check --private-dir "$work/handoff"
echo 'ALL STAGES PASSED: 20 ses-02 TEDANA/confound runs, canonical QC, scanner-era QC, baseline handoff.'
echo 'This is technical validation, not a new exclusion decision or final paper-cohort approval.'
