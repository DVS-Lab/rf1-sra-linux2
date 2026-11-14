#!/usr/bin/env python3
"""Survey RF1 storage from filesystem metadata only; never modify study files."""
import argparse
from collections import defaultdict
from dataclasses import dataclass
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys
from typing import Callable


RF1_PROJECT = re.compile(r"(?:rf1(?:-sra)?(?:-[A-Za-z0-9_-]+)?|sharedreward-aging|tubric-qa)")
WORK_GROUPS = (
    ("repair stages", ("reviewed-source-repairs-", "11935-final-repair-", "11935-initialization-",
                       "11935-", "reviewed-repair-", "sbref-repair-")),
    ("repair archives", ("reviewed-install-archive-",)),
    ("paired/group analysis inputs", ("randomise-", "socialdoors-randomise-", "coverage95-",
                                       "paired-difference", "paired-paper-", "wave1-randomise.")),
    ("batch plans and runtime", ("no-tedana-", "missing-first-levels.", "stage1-linux2.", "venv")),
    ("QC work", ("tubric-qa-", "xa60-coverage-", "cohort-smoothness-", "task-availability-",
                 "scanner-era-", "dicom-", "t1w-")),
)


@dataclass
class Scope:
    label: str
    path: Path
    classify: Callable[[Path], str]


@dataclass
class Usage:
    allocated: int = 0
    apparent: int = 0
    files: int = 0

    def add(self, info):
        self.allocated += info.st_blocks * 512
        self.apparent += info.st_size
        self.files += 1


def project_bucket(relative):
    top, *rest = relative.parts
    if top == "work" and rest:
        for group, prefixes in WORK_GROUPS:
            if rest[0].startswith(prefixes):
                return f"work / {group}"
        return "work / other"
    if top == "derivatives" and rest:
        family = rest[0]
        if family == "tedana-audit" and len(rest) > 1:
            if rest[1] == "cohort-pca-v1":
                return "derivatives / TEDANA cohort PCA"
            return "derivatives / other TEDANA experiments"
        if family.startswith(("smoothness-evaluation-", "smoothed")):
            return "derivatives / smoothing variants"
        if family.startswith("fsl-no-tedana-"):
            if family in {"fsl-no-tedana-age55", "fsl-no-tedana-wave1"}:
                return f"derivatives / {family}"
            return "derivatives / other base-only FEAT"
        if family == "fsl" and len(rest) > 1:
            if rest[1].startswith(("confounds_tedana", "confounds_base")):
                return "derivatives / fsl / confounds"
            if rest[1].startswith(("L3", "randomise")):
                return "derivatives / fsl / group analyses"
            if any(".gfeat" in part for part in rest[1:]):
                return "derivatives / fsl / paired and group FEAT"
            if any(".feat" in part for part in rest[1:]):
                return "derivatives / fsl / first levels"
        if family in {"fmriprep", "freesurfer", "warpkit", "tedana", "mriqc", "fsl", "source_repairs",
                      "fmriprep_geometry", "randomise", "smoothed", "smoothness"}:
            return f"derivatives / {family}"
        return "derivatives / other"
    if top in {"bids", "sourcedata", "scratch", "logs", "qc", "results", "data", ".git", ".venv"}:
        return top
    return "other"


def scratch_bucket(relative):
    top = relative.parts[0]
    return next((name for name in ("fmriprep", "mriqc", "heudiconv", "prepdata", "warpkit", "tedana")
                 if top.startswith(name)), "other")


def artifact_kind(path, size):
    name = path.name.lower()
    if not name.endswith((".nii", ".nii.gz")):
        if name.endswith((".zip", ".tar", ".tar.gz", ".tgz")):
            return "archives"
        return "other files"
    if re.search(r"_desc-(optcom|combined)_bold\.nii", name):
        return "optimally combined BOLD"
    if re.search(r"_desc-denoised(?:fullgrid)?_bold\.nii", name):
        return "denoised BOLD"
    if re.search(r"_echo-\d+.*_desc-preproc_bold\.nii", name):
        return "preprocessed echoes"
    if name.startswith(("filtered_func_data.", "prefiltered_func_data", "res4d.")):
        return "FEAT intermediate series"
    if "_desc-preproc_bold.nii" in name:
        return "preprocessed BOLD"
    if "_desc-smoothtofwhm" in name:
        return "target-smoothed BOLD"
    if "difference_4d" in name or name in {"average.nii.gz", "social_specific.nii.gz"}:
        return "group COPE stacks"
    if "_bold.nii" in name or size > 40 * 1024**2:
        return "other BOLD or large NIfTI"
    return "other NIfTI"


class Inventory:
    def __init__(self):
        self.roots = defaultdict(Usage)
        self.buckets = defaultdict(Usage)
        self.types = defaultdict(Usage)
        self.hardlinks = set()
        self.notes = defaultdict(int)

    def walk(self, label, root, classify, other_roots=()):
        try:
            info = root.lstat()
        except FileNotFoundError:
            self.notes[label, "root not present"] += 1
            return
        except OSError:
            self.notes[label, "unreadable"] += 1
            return
        if not stat.S_ISDIR(info.st_mode):
            self.notes[label, "non-directory or symlink root skipped"] += 1
            return
        dirs = [root]
        self.roots[label]
        while dirs:
            folder = dirs.pop()
            try:
                with os.scandir(folder) as children:
                    for entry in children:
                        try:
                            info = entry.stat(follow_symlinks=False)
                        except FileNotFoundError:
                            self.notes[label, "entries disappeared while listing"] += 1
                            continue
                        except OSError:
                            self.notes[label, "unreadable"] += 1
                            continue
                        if stat.S_ISDIR(info.st_mode):
                            path = Path(entry.path)
                            if path in other_roots or path.name == ".zfs":
                                continue
                            dirs.append(path)
                        elif stat.S_ISLNK(info.st_mode):
                            self.notes[label, "symlinks not followed"] += 1
                        elif stat.S_ISREG(info.st_mode):
                            if info.st_nlink > 1:
                                key = info.st_dev, info.st_ino
                                if key in self.hardlinks:
                                    self.notes[label, "hard-link aliases not counted twice"] += 1
                                    continue
                                self.hardlinks.add(key)
                            relative = Path(entry.path).relative_to(root)
                            bucket = classify(relative)
                            self.roots[label].add(info)
                            self.buckets[label, bucket].add(info)
                            self.types[label, bucket, artifact_kind(relative, info.st_size)].add(info)
            except FileNotFoundError:
                self.notes[label, "entries disappeared while listing"] += 1
            except OSError:
                self.notes[label, "unreadable"] += 1


def rows(title, data, limit=None, minimum=0):
    print(f"\n{title}\nAllocated GiB\tApparent GiB\tFiles\tScope")
    ranked = sorted((key for key in data if data[key].allocated >= minimum),
                    key=lambda key: (-data[key].allocated, key))
    for key in ranked[:limit]:
        value = data[key]
        label = " / ".join(key) if isinstance(key, tuple) else key
        print(f"{value.allocated / 1024**3:.2f}\t{value.apparent / 1024**3:.2f}\t{value.files}\t{label}")


def command(label, args, keep=None):
    print(f"\n{label}", flush=True)
    exe = shutil.which(args[0])
    if exe is None and args[0] in {"zfs", "zpool"} and Path("/sbin", args[0]).is_file():
        exe = str(Path("/sbin", args[0]))
    if not exe:
        print("Command not available.")
        return
    result = subprocess.run([exe, *args[1:]], capture_output=True, text=True)
    if result.returncode:
        print(f"Command unavailable or not permitted (exit {result.returncode}).")
        return
    for line in result.stdout.splitlines():
        if keep is None or keep(line):
            print(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("/ZPOOL/data"))
    parser.add_argument("--scratch-root", type=Path, help="Defaults to SCRATCH_ROOT or DATA_ROOT/scratch")
    args = parser.parse_args()
    base = args.data_root.resolve()
    projects = base/"projects"
    if not projects.is_dir():
        parser.error("Data root has no projects directory")
    scratch_base = args.scratch_root or Path(os.environ.get("SCRATCH_ROOT", base/"scratch"))
    scratch = scratch_base/pwd.getpwuid(os.getuid()).pw_name
    print("Read-only RF1 workspace survey. File sizes are not a reclaim estimate.", flush=True)
    mounts = [str(projects), *([str(scratch)] if scratch.is_dir() else []),
              str(Path(os.environ.get("TMPDIR", "/tmp")))]
    command("Filesystem capacity", ["df", "-hP", *mounts])
    command("Filesystem inode usage", ["df", "-iP", *mounts])
    command("ZFS pools", ["zpool", "list", "-o", "name,size,alloc,free,cap,health"])
    fields = "name,used,avail,refer,usedbysnapshots,usedbydataset,usedbychildren,mountpoint"
    command("ZFS dataset accounting", ["zfs", "list", "-o", fields],
            lambda line: line.startswith("NAME") or (line.split() and
                Path(line.split()[-1]).is_relative_to(base.parent)))
    inv = Inventory()
    scopes = [Scope(p.name, p, project_bucket) for p in sorted(projects.iterdir())
              if RF1_PROJECT.fullmatch(p.name)]
    source = base/"sourcedata/sourcedata"
    for name in ("rf1-sra", "rf1-sra-exclusions"):
        scopes.append(Scope(f"source / {name}", source/name, lambda _: "source files"))
    scopes.append(Scope("scratch (current account)", scratch, scratch_bucket))
    for scope in scopes:
        print(f"Scanning {scope.label}", flush=True)
        inv.walk(scope.label, scope.path, scope.classify, {s.path for s in scopes if s != scope})
    rows("Project / source / scratch totals", inv.roots)
    rows("Largest storage buckets", inv.buckets, limit=40)
    rows("Largest bucket and file-type combinations (>= 1 GiB)", inv.types, limit=30, minimum=1024**3)
    print("\nInventory notes")
    for (label, note), count in sorted(inv.notes.items()):
        print(f"{label}\t{count}\t{note}")
    print("No study files modified. Running jobs can change sizes during this snapshot.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
