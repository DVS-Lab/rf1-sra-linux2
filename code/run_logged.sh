#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: bash run_logged.sh [--label LABEL] -- COMMAND [ARGS...] [--check CHECK_COMMAND [ARGS...]]

Runs COMMAND, writes one timestamped raw log under ignored logs/runs/, and
writes one compact Git-trackable record under logs/records/.
USAGE
}

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=code/pipeline_common.sh
source "${scriptdir}/pipeline_common.sh"
rf1_load_config

label=""
while (($#)); do
  case "$1" in
    --label)
      label="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

if (($# == 0)); then
  usage
  exit 2
fi

cmd=()
check_cmd=()
while (($#)); do
  if [[ "$1" == "--check" ]]; then
    shift
    check_cmd=("$@")
    break
  fi
  cmd+=("$1")
  shift
done

if ((${#cmd[@]} == 0)); then
  usage
  exit 2
fi

if [[ -z "$label" ]]; then
  label="$(basename "${cmd[0]}")"
  label="${label%.*}"
fi
label="$(printf '%s' "$label" | tr -c 'A-Za-z0-9_.-' '_')"
timestamp="$(date +%Y%m%d-%H%M%S)"
raw_dir="${PROJECT_ROOT}/logs/runs"
record_dir="${PROJECT_ROOT}/logs/records"
raw_log="${raw_dir}/${timestamp}_${label}.log"
record="${record_dir}/${timestamp}_${label}.md"
status_file="${raw_log}.status"
mkdir -p "$raw_dir" "$record_dir"

git_commit="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
branch="$(git -C "$PROJECT_ROOT" branch --show-current 2>/dev/null || echo unknown)"
host="$(hostname 2>/dev/null || echo unknown)"
user="$(whoami 2>/dev/null || echo unknown)"
cwd="$(pwd)"

command_string="$(printf '%q ' "${cmd[@]}")"
check_string=""
if ((${#check_cmd[@]})); then
  check_string="$(printf '%q ' "${check_cmd[@]}")"
fi

echo "Writing raw log: $raw_log"
echo "Writing run record: $record"

set +e
(
  command_status=0
  check_status=0
  final_status=0

  echo "RUN START: ${timestamp}"
  echo "PROJECT_ROOT: ${PROJECT_ROOT}"
  echo "GIT: ${branch} ${git_commit}"
  echo "HOST: ${host}"
  echo "USER: ${user}"
  echo "PWD: ${cwd}"
  echo "COMMAND: ${command_string}"
  echo

  "${cmd[@]}"
  command_status=$?
  echo
  echo "COMMAND EXIT: ${command_status}"

  if ((${#check_cmd[@]})); then
    echo
    echo "CHECK COMMAND: ${check_string}"
    echo
    "${check_cmd[@]}"
    check_status=$?
    echo
    echo "CHECK EXIT: ${check_status}"
  fi

  final_status="$command_status"
  if ((check_status != 0)); then
    final_status="$check_status"
  fi
  {
    printf 'COMMAND_STATUS=%s\n' "$command_status"
    printf 'CHECK_STATUS=%s\n' "$check_status"
  } > "$status_file"
  exit "$final_status"
) 2>&1 | tee "$raw_log"
run_status=${PIPESTATUS[0]}
set -e

COMMAND_STATUS="unknown"
CHECK_STATUS="none"
if [[ -f "$status_file" ]]; then
  # shellcheck disable=SC1090
  source "$status_file"
  rm -f "$status_file"
fi

summary="$(grep -E 'CHECK (PASSED|FAILED):' "$raw_log" | tail -n 1 || true)"
[[ -n "$summary" ]] || summary="No CHECK PASSED/FAILED line found."

{
  echo "# Run Record: ${label}"
  echo
  echo "- Timestamp: ${timestamp}"
  echo "- Branch: ${branch}"
  echo "- Commit: ${git_commit}"
  echo "- Host: ${host}"
  echo "- User: ${user}"
  echo "- Working directory: \`${cwd}\`"
  echo "- Raw log: \`${raw_log}\`"
  echo "- Command exit: ${COMMAND_STATUS}"
  echo "- Check exit: ${CHECK_STATUS}"
  echo "- Summary: ${summary}"
  echo
  echo "## Command"
  echo
  echo '```bash'
  echo "$command_string"
  echo '```'
  if ((${#check_cmd[@]})); then
    echo
    echo "## Check"
    echo
    echo '```bash'
    echo "$check_string"
    echo '```'
  fi
} > "$record"

echo "Run record saved: $record"
exit "$run_status"
