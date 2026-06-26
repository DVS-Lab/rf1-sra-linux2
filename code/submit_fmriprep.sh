#!/usr/bin/env bash
set -euo pipefail

scriptdir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
exec bash "${scriptdir}/run_fmriprep.sh" --sublist "${scriptdir}/sublist_ses-2.txt" --jobs 5 "$@"
