#!/usr/bin/env python
import os, shlex, datetime, glob, re, json, sys
from nipype import Workflow, Node
from nipype.interfaces.base import CommandLine

# ── CONFIGURATION ───────────────────────────────────────────────────────────────
SUBLIST_FILE = os.path.join(os.path.dirname(__file__), "sublist_new.txt")
SESSIONS     = ["01", "02"]
SOURCEDATA   = "/ZPOOL/data/sourcedata/sourcedata/rf1-sra"

# OPTIMIZED FOR: AMD Threadripper PRO 5995WX (128 threads), 251GB RAM, Local ZFS
MAX_CONCURRENT_SUBJECTS = int(os.environ.get("RF1_MAX_SUBJECTS", "16"))
CPUS_PER_SUBJECT = int(os.environ.get("RF1_CPUS_PER_SUBJECT", "6"))

# ────────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR   = os.path.dirname(SCRIPT_DIR)
LOG_FILE   = os.path.join(PROJ_DIR, "rf1_forhpc_preprocessing.log")
SESSION_CACHE = os.path.join(SCRIPT_DIR, ".session_cache.json")

# Cleanup from previous batch of subjects before processing new subjects so locks/caches don't impede
# Remove lock file from previous runs
lock_file = os.path.join(PROJ_DIR, ".sourcedata_scan.lock")
if os.path.isdir(lock_file):
    try:
        os.rmdir(lock_file)
        print(f" Removed lock: {lock_file}")
    except Exception as e:
        print(f"Could not remove lock (may be in use): {e}")

# Remove session cache
if os.path.exists(SESSION_CACHE):
    try:
        os.remove(SESSION_CACHE)
        print(f"Removed session cache: {SESSION_CACHE}")
    except Exception as e:
        print(f"Could not remove cache: {e}")

# Clean up old nipype work directory (optional - comment out if you want to keep it)
nipype_work = os.path.join(PROJ_DIR, "nipype_work")
if os.path.isdir(nipype_work):
    import shutil
    try:
        shutil.rmtree(nipype_work)
        print(f"Removed nipype work: {nipype_work}")
    except Exception as e:
        print(f"Could not remove nipype work: {e}")

print("Cleanup complete.\n")

with open(SUBLIST_FILE) as f:
    SUBJECTS = [ln.strip() for ln in f if ln.strip()]

j   = os.path.join
q   = lambda *a: " ".join(shlex.quote(x) for x in a)
cmd = lambda s, *args: q("bash", j(SCRIPT_DIR, s), *args)

def session_has_raw_fast(sub: str, ses: str) -> bool:
    """
    Faster check: only look for the scans directory existence and check if ANY
    .dcm file exists (not counting them all). Uses os.path.exists instead of glob
    for initial directory checks.
    """
    if ses == "02":
        scandir = j(SOURCEDATA, f"Smith-SRA-{sub}-2", f"Smith-SRA-{sub}-2", "scans")
    else:
        scandir = j(SOURCEDATA, f"Smith-SRA-{sub}", f"Smith-SRA-{sub}", "scans")
    
    # Quick exit if scans dir doesn't exist
    if not os.path.isdir(scandir):
        return False
    
    # Use os.walk with early termination instead of glob (much faster)
    try:
        for root, dirs, files in os.walk(scandir):
            if 'DICOM' in root and any(f.endswith('.dcm') for f in files):
                return True
            # Limit depth to avoid deep recursion
            if root.count(os.sep) - scandir.count(os.sep) > 5:
                dirs[:] = []  # Don't recurse deeper
    except (OSError, PermissionError):
        return False
    
    return False

def build_session_cache(force=False):
    """
    Pre-scan all subjects and cache which sessions exist.
    This runs ONCE at startup instead of during workflow construction.
    """
    if os.path.exists(SESSION_CACHE) and not force:
        print(f"Loading cached session info from {SESSION_CACHE}")
        with open(SESSION_CACHE) as f:
            return json.load(f)
    
    print(f"Scanning {len(SUBJECTS)} subjects for available sessions...")
    print("This may take a few minutes on first run...")
    
    cache = {}
    for i, sub in enumerate(SUBJECTS, 1):
        if i % 10 == 0:
            print(f"  Scanned {i}/{len(SUBJECTS)} subjects...", flush=True)
        
        present = []
        for ses in SESSIONS:
            try:
                if session_has_raw_fast(sub, ses):
                    present.append(ses)
            except Exception as e:
                print(f"  Warning: Error checking sub-{sub} ses-{ses}: {e}", file=sys.stderr)
                continue
        
        # Fallback: check if BIDS already exists
        if not present:
            for ses in SESSIONS:
                bids_ses = j(PROJ_DIR, "bids", f"sub-{sub}", f"ses-{ses}")
                if os.path.isdir(bids_ses):
                    present.append(ses)
        
        cache[sub] = sorted(set(present))
    
    # Save cache
    with open(SESSION_CACHE, 'w') as f:
        json.dump(cache, f, indent=2)
    
    print(f"Session cache saved to {SESSION_CACHE}")
    return cache

def write_wave2_list(session_cache):
    subs_with_ses02 = [s for s, sessions in session_cache.items() if "02" in sessions]
    out_path = j(SCRIPT_DIR, "sublist_wave2.txt")
    with open(out_path, "w") as f:
        for s in sorted(subs_with_ses02):
            f.write(f"{s}\n")
    return subs_with_ses02

# Build session cache BEFORE workflow construction
print("="*80)
print("PHASE 1: Scanning for available sessions...")
print("="*80)
session_cache = build_session_cache(force=False)

# Filter to only subjects that have at least one session
subjects_to_process = [s for s in SUBJECTS if session_cache.get(s, [])]
subjects_skipped = [s for s in SUBJECTS if not session_cache.get(s, [])]

print(f"\nSubjects with data: {len(subjects_to_process)}")
print(f"Subjects skipped (no sessions): {len(subjects_skipped)}")
if subjects_skipped:
    print(f"  Skipped: {', '.join(subjects_skipped[:10])}" + 
          (f" ... and {len(subjects_skipped)-10} more" if len(subjects_skipped) > 10 else ""))

subs_with_ses02 = write_wave2_list(session_cache)

os.makedirs(PROJ_DIR, exist_ok=True)
with open(LOG_FILE, "a") as lf:
    lf.write("\n" + "="*80 + "\n")
    lf.write(f"RF1 preprocessing launch: {datetime.datetime.now().isoformat()}\n")
    lf.write(f"Subjects total: {len(SUBJECTS)}\n")
    lf.write(f"Subjects to process: {len(subjects_to_process)}\n")
    lf.write(f"Subjects skipped: {len(subjects_skipped)}\n")
    lf.write(f"Max concurrent subjects: {MAX_CONCURRENT_SUBJECTS}\n")
    lf.write(f"CPUs per subject: {CPUS_PER_SUBJECT}\n")
    lf.write(f"Sessions (requested): {', '.join(SESSIONS)}\n")
    lf.write(f"Wave2 (have ses-02): {len(subs_with_ses02)}\n")
    lf.write("="*80 + "\n")

ENV_BOOTSTRAP = r'''
set -euo pipefail
U0="$(id -un)"; U1="${USER:-$U0}"; U2="${U1%%@*}"

for root in \
  "/ZPOOL/data/tools/anaconda/${U0}/anaconda3" "/ZPOOL/data/tools/anaconda/${U0}/miniconda3" \
  "/ZPOOL/data/tools/anaconda/${U2}/anaconda3" "/ZPOOL/data/tools/anaconda/${U2}/miniconda3" \
  "/ZPOOL/data/tools/anaconda/${U1}/anaconda3" "/ZPOOL/data/tools/anaconda/${U1}/miniconda3"
do
  if [ -f "$root/etc/profile.d/conda.sh" ]; then
    . "$root/etc/profile.d/conda.sh"
    CONDA_READY=1
    break
  fi
done

if [ -z "${CONDA_READY:-}" ]; then
  for c in "/opt/conda/etc/profile.d/conda.sh" "/usr/local/conda/etc/profile.d/conda.sh"; do
    if [ -f "$c" ]; then
      . "$c"
      CONDA_READY=1
      break;
    fi
  done
fi

if [ -z "${CONDA_READY:-}" ] && command -v conda >/dev/null 2>&1; then
  eval "$(conda shell.bash hook)" || true
  CONDA_READY=1
fi

if [ -n "${CONDA_READY:-}" ]; then
  conda activate base || true
else
  echo "WARNING: conda.sh not found; proceeding without 'conda activate'." >&2
fi

if ! command -v pydeface >/dev/null 2>&1; then
  echo "ERROR: pydeface not found on PATH." >&2
  exit 127
fi
if ! command -v singularity >/dev/null 2>&1 && ! command -v apptainer >/dev/null 2>&1; then
  echo "ERROR: Neither singularity nor apptainer found on PATH." >&2
  exit 127
fi
if [ -z "${FSLDIR:-}" ]; then
  for d in "/usr/local/fsl" "/opt/fsl"; do [ -d "$d" ] && export FSLDIR="$d" && break; done
fi
if [ -n "${FSLDIR:-}" ] && [ -f "$FSLDIR/etc/fslconf/fsl.sh" ]; then
  . "$FSLDIR/etc/fslconf/fsl.sh"; export PATH="$PATH:$FSLDIR/bin"
fi
[ -d "/ZPOOL/data/tools/templateflow" ] && export TEMPLATEFLOW_HOME="/ZPOOL/data/tools/templateflow"
[ -d "/ZPOOL/data/tools/mplconfigdir" ] && export MPLCONFIGDIR="/ZPOOL/data/tools/mplconfigdir"

export OMP_NUM_THREADS="''' + str(max(1, CPUS_PER_SUBJECT // 2)) + '''"
export MKL_NUM_THREADS="''' + str(max(1, CPUS_PER_SUBJECT // 2)) + '''"
export OPENBLAS_NUM_THREADS="''' + str(max(1, CPUS_PER_SUBJECT // 2)) + '''"
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="''' + str(max(1, CPUS_PER_SUBJECT // 2)) + '''"

export SINGULARITY_CACHEDIR="${TMPDIR:-/tmp}/singularity-cache-$$"
export APPTAINER_CACHEDIR="${TMPDIR:-/tmp}/apptainer-cache-$$"
mkdir -p "$SINGULARITY_CACHEDIR" "$APPTAINER_CACHEDIR" 2>/dev/null || true
'''

def wrap_logged(sub, chain):
    start = f'echo "=== START sub-{sub} ==="'
    endok = f'echo "=== END sub-{sub} STATUS=OK ==="'
    endfl = f"trap 'rc=$?; echo \"=== END sub-{sub} STATUS=FAIL rc=${{rc}} ===\"' ERR"
    body  = f"{ENV_BOOTSTRAP}\n{endfl}; {start}; {chain} ; {endok}"
    prefixer = (
        f'''stdbuf -oL -eL '''
        f'''awk '{{printf "%s [sub-{sub}] %s\\n", strftime("[%Y-%m-%d %H:%M:%S]"), $0}}' '''
        f'''>> {shlex.quote(LOG_FILE)}'''
    )
    return f'({body}) 2>&1 | {prefixer}'

def per_subject_chain(sub: str, present_ses: list) -> str:
    """Build processing chain using pre-cached session list."""
    if not present_ses:
        return f'echo "Skipping sub-{sub}: no sessions present"'

    skip_check = (
        f"[ -f {shlex.quote(j(PROJ_DIR, 'bids', f'sub-{sub}', '.processing_complete'))} ] && "
        f"{{ echo 'Subject {sub} already complete, skipping'; exit 0; }}"
    )

    prep_groups = []
    for ses in present_ses:
        # Use rate-limited prepdata to prevent I/O stampede
        prep_groups.append("{ " + f"{cmd('prepdata_ratelimited.sh', sub, ses)}" + " ; } &")
    par_prep = " ".join(prep_groups) + f" wait"

    warp_groups = []
    for ses in present_ses:
        discover_and_warp = (
            "{ "
            "bash -lc " +
            shlex.quote(
                "set -euo pipefail; "
                f"PROJ_DIR={shlex.quote(PROJ_DIR)}; sub={shlex.quote(sub)}; ses={shlex.quote(ses)}; "
                "bids_func=\"$PROJ_DIR/bids/sub-${sub}/ses-${ses}/func\"; "
                "if [ -d \"$bids_func\" ]; then "
                "  python - <<'PY'\n"
                "import os, re, glob\n"
                f"PROJ_DIR={repr(PROJ_DIR)}\n"
                f"sub={repr(sub)}; ses={repr(ses)}\n"
                "bids_func=os.path.join(PROJ_DIR,'bids',f'sub-{sub}',f'ses-{ses}','func')\n"
                "pat=re.compile(rf'^sub-{sub}_ses-{ses}_task-([A-Za-z0-9]+)_run-([0-9]+)_echo-1_part-mag_bold\\.json$')\n"
                "candidates=[]\n"
                "if os.path.isdir(bids_func):\n"
                "  for fn in glob.glob(os.path.join(bids_func,'*echo-1_part-mag_bold.json')):\n"
                "    base=os.path.basename(fn)\n"
                "    m=pat.match(base)\n"
                "    if not m:\n"
                "      continue\n"
                "    task, run = m.group(1), m.group(2)\n"
                "    def p(suffix):\n"
                "      return os.path.join(bids_func, f'sub-{sub}_ses-{ses}_task-{task}_run-{run}_{suffix}')\n"
                "    required = [\n"
                "      p('echo-1_part-mag_bold.nii.gz'), p('echo-2_part-mag_bold.nii.gz'),\n"
                "      p('echo-3_part-mag_bold.nii.gz'), p('echo-4_part-mag_bold.nii.gz'),\n"
                "      p('echo-1_part-phase_bold.nii.gz'), p('echo-2_part-phase_bold.nii.gz'),\n"
                "      p('echo-3_part-phase_bold.nii.gz'), p('echo-4_part-phase_bold.nii.gz'),\n"
                "      p('echo-1_part-phase_bold.json'),  p('echo-2_part-phase_bold.json'),\n"
                "      p('echo-3_part-phase_bold.json'),  p('echo-4_part-phase_bold.json'),\n"
                "    ]\n"
                "    if all(os.path.exists(x) for x in required):\n"
                "      candidates.append((task, int(run)))\n"
                "for task, run in sorted(candidates, key=lambda x:(x[0], x[1])):\n"
                "  print(task, run)\n"
                "PY\n"
                "fi"
            ) +
            f" | xargs -P {CPUS_PER_SUBJECT // 2} -n 2 bash -c '"
            + f"bash {shlex.quote(os.path.join(SCRIPT_DIR,'warpkit.sh'))} "
              f"{shlex.quote(sub)} {shlex.quote(ses)} \"$0\" \"$1\"' ; }} &"
        )
        warp_groups.append(discover_and_warp)

    par_warp = " ".join(warp_groups) + " wait"

    add_intended = q("python", os.path.join(SCRIPT_DIR, "addIntendedFor-fmap.py"), 
                     os.path.join(PROJ_DIR, "bids"))
    mark_complete = f"touch {shlex.quote(j(PROJ_DIR, 'bids', f'sub-{sub}', '.processing_complete'))}"

    return " ; ".join([skip_check, par_prep, par_warp, add_intended, mark_complete])

# ── Build workflow ─────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("PHASE 2: Building Nipype workflow...")
print("="*80)

wf = Workflow(name="rf1_prep_with_warpkit", base_dir=j(PROJ_DIR, "nipype_work"))

for sub in subjects_to_process:
    present_ses = session_cache[sub]
    node = Node(CommandLine(command="/bin/bash"), name=f"sub_{sub}")
    node.inputs.args = f"-lc {shlex.quote(wrap_logged(sub, per_subject_chain(sub, present_ses)))}"
    node.interface.terminal_output = "allatonce"
    wf.add_nodes([node])

print(f"Workflow created with {len(subjects_to_process)} subjects")
print(f"Starting execution with {MAX_CONCURRENT_SUBJECTS} concurrent subjects...")
print(f"Monitor progress: tail -f {LOG_FILE}")
print("="*80 + "\n")

if __name__ == "__main__":
    wf.run(plugin="MultiProc", plugin_args={
        "n_procs": MAX_CONCURRENT_SUBJECTS,
        "raise_insufficient": False
    })
