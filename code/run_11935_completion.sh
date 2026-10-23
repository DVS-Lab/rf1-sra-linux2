#!/usr/bin/env bash
set -euo pipefail
umask 0000

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="$(dirname "$scriptdir")"
cd "$project"
python="${AUDIT_PYTHON:-/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python}"
export PATH="$(dirname "$python"):$PATH"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
repair="${REPAIR_DIR:-${project}/work/11935-final-repair-v1}"
socdoors="${SOCDOORS_ROOT:-/ZPOOL/data/projects/rf1-sra-socdoors}"
cohort="${COHORT_ROOT:-${project}/derivatives/tedana-audit/cohort-pca-v1}"
stage="${repair}/sub-11935-project"
archive="${repair}/replaced-originals"
receipt="${archive}/promotion.json"
models="${repair}/models"

case "${1:-}" in
  stage)
    "$python" code/complete_11935_repair.py plan --work-dir "$repair"
    "$python" code/complete_11935_repair.py build --work-dir "$repair" --jobs "${REPAIR_JOBS:-8}"
    "$python" code/complete_11935_repair.py check --work-dir "$repair" --jobs "${REPAIR_JOBS:-8}"
    ;;
  promote)
    [[ "${2:-}" == "--approve-images" ]] || {
      echo "Review both corrected native/MNI montages, then use promote --approve-images." >&2
      exit 2
    }
    args=(--project-root "$project" --staged-project "$stage" --archive-root "$archive"
          --socdoors-root "$socdoors" --cohort-root "$cohort")
    "$python" code/promote_11935.py plan "${args[@]}"
    "$python" code/promote_11935.py promote "${args[@]}" --approve-images
    "$python" code/promote_11935.py check --receipt "$receipt"
    "$python" code/revise_tedana_cohort.py plan --project-root "$project" --audit-root "$cohort" \
      --promotion-receipt "$receipt" --archive-root "$repair/cohort-revision"
    "$python" code/revise_tedana_cohort.py apply --project-root "$project" --audit-root "$cohort" \
      --promotion-receipt "$receipt" --archive-root "$repair/cohort-revision"
    ;;
  finish)
    printf '11935\n' > "$repair/subject.txt"
    bash code/check_fmriprep.sh --sublist "$repair/subject.txt"
    bash code/check_tedana.sh --sublist "$repair/subject.txt" --session 01
    "$python" code/genTedanaConfounds.py --sublist "$repair/subject.txt" --session 01 --check
    "$python" code/check_events.py --subject 11935 --session 01 --quiet-ok
    args=(--project-root "$project" --socdoors-root "$socdoors" --private-dir "$models"
          --promotion-receipt "$receipt")
    if [[ ! -f "$models/plan.json" ]]; then
      "$python" code/rebuild_11935_models.py prepare "${args[@]}"
    fi
    "$python" code/rebuild_11935_models.py run "${args[@]}"
    "$python" code/rebuild_11935_models.py check "${args[@]}"
    "$python" code/build_run_qc.py build --overwrite
    "$python" code/build_run_qc.py check
    "$python" code/build_scanner_era_qc.py build --overwrite
    "$python" code/build_scanner_era_qc.py check
    "$python" code/audit_tedana.py build --overwrite
    "$python" code/audit_tedana.py check
    "$python" "$socdoors/code/build_L1_manifest.py" --sublist "$repair/subject.txt" \
      --bids-root "$project/bids" --fmriprep-root "$project/derivatives/fmriprep" \
      --confounds-root "$project/derivatives/fsl/confounds_tedana" --sessions 01 \
      --output "$repair/technical-L1.tsv" --missing-output "$repair/technical-missing.tsv"
    "$python" "$socdoors/code/build_L2_manifest.py" --l1-manifest "$repair/technical-L1.tsv" \
      --output "$repair/technical-L2.tsv"
    "$python" -c 'import csv,sys; rows=list(csv.DictReader(open(sys.argv[1]),delimiter="\t")); assert {(r["subject"],r["session"],r["task"],r["run"]) for r in rows} == {("11935","01",t,"1") for t in ("doors","socialdoors")} and len(rows)==2, "11935 technical handoff incomplete"' \
      "$repair/technical-L1.tsv"
    echo "Canonical and no-TEDANA activation L1/L2 verified; QC refreshed without changing exclusions."
    echo "Read subject_ready.tsv in $models; Jacob must refresh affected L3 inputs/models."
    ;;
  variants)
    "$python" code/benchmark_tedana_cohort.py run --project-root "$project" --audit-root "$cohort" \
      --jobs "${COHORT_JOBS:-20}"
    ;;
  *)
    echo "Usage: bash code/run_11935_completion.sh stage|promote --approve-images|finish|variants" >&2
    exit 2
    ;;
esac
