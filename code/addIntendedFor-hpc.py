#!/usr/bin/env python3
import os, json, re
from pathlib import Path
from glob import glob

HERE = Path(__file__).resolve().parent
BIDS = (HERE / ".." / "bids").resolve()

def rel_from_subj(p: Path, subj: str) -> str:
    """Return POSIX relative path anchored at sub-XXXX/…"""
    sp = p.as_posix()
    i = sp.index(subj)
    return sp[i:]

def find_mag_targets(subj: str, ses: str|None, task: str|None, run: str|None, func_dir: Path):
    """Prefer echo-specific MAG BOLD, then echo-specific MAG SBRef, then non-echo MAG BOLD/SBRef."""
    if not (task and run):
        return []
    ses_tag = ses if ses else "ses-01"  # best guess if missing in filename
    base = f"{subj}_{ses_tag}_task-{task}_run-{run}"

    patterns = [
        f"{base}_echo-*_part-mag_bold.nii.gz",
        f"{base}_echo-*_part-mag_sbref.nii.gz",
        f"{base}_part-mag_bold.nii.gz",
        f"{base}_part-mag_sbref.nii.gz",
    ]
    for pat in patterns:
        found = sorted(func_dir.glob(pat))
        found = [x for x in found if "_part-phase_" not in x.name]
        if found:
            return found
    return []

def main():
    subs = sorted([d for d in BIDS.iterdir() if d.is_dir() and d.name.startswith("sub-")])
    print("subjects:", len(subs))

    for subj_path in subs:
        subj = subj_path.name
        ses_dirs = sorted([d for d in subj_path.iterdir() if d.is_dir() and d.name.startswith("ses-")])
        if not ses_dirs:
            ses_dirs = [subj_path]  # single-session layout

        print("subject:", subj, "sessions:", [d.name if d!=subj_path else "(no-ses)" for d in ses_dirs])

        for base in ses_dirs:
            ses = base.name if base.name.startswith("ses-") else ""
            fmap_dir = base / "fmap"
            func_dir = base / "func"
            if not (fmap_dir.is_dir() and func_dir.is_dir()):
                continue

            fmap_jsons = sorted(fmap_dir.glob("*.json"))
            bold_files = sorted(func_dir.glob("*_bold.nii.gz"))
            if not fmap_jsons or not bold_files:
                continue

            for jpath in fmap_jsons:
                fname = jpath.name
                # Parse task/run from the fmap filename
                m_task = re.search(r"task-([A-Za-z0-9]+)", fname)
                m_run  = re.search(r"run-([0-9]+)", fname)
                task = m_task.group(1) if m_task else None
                run  = m_run.group(1)  if m_run  else None

                with open(jpath, "r") as f:
                    data = json.load(f)

                # Default: empty / don’t link if not run-specific
                intended_rel = []

                if task and run:
                    targets = find_mag_targets(subj, ses if ses else None, task, run, func_dir)
                    intended_rel = [rel_from_subj(t, subj) for t in targets]

                # Write the tight set; never include part-phase
                if intended_rel:
                    data["IntendedFor"] = intended_rel
                else:
                    # Ensure we don't accidentally re-introduce global links
                    data.pop("IntendedFor", None)

                # Fieldmap hygiene
                if "fieldmap" in fname:
                    data["Units"] = data.get("Units", "Hz")
                    data.pop("EchoTime1", None)
                    data.pop("EchoTime2", None)

                with open(jpath, "w") as f:
                    json.dump(data, f, indent=2, sort_keys=True)

                print("updated:", jpath.relative_to(BIDS), "links:", len(data.get("IntendedFor", [])))

if __name__ == "__main__":
    main()

