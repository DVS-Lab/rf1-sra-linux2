#!/usr/bin/env python3
"""Stage the reviewed 11935 Faces/Doors repair with the tested masking backport."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from types import SimpleNamespace

import nibabel as nib
import numpy as np
import pandas as pd

import run_11935_initialization as initialization
import run_reviewed_source_repairs as reviewed
from build_run_qc import compute_coverage
from inspect_xa60_coverage import montage

ROOT = Path(__file__).resolve().parents[1]
TASKS = ("doors", "socialdoors")
PREFIXES = tuple(f"sub-11935_ses-01_task-{task}_run-1_" for task in TASKS)
TARGET = "qc/reference/" + initialization.TARGET
ORIGINAL_UTIL_SHA = "183077163f8334e8a7fab2e198a4435337949afce819865a8ff6531ec407df56"


def require(value, message):
    if not value:
        raise ValueError(message)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    reviewed.write_json(path, value)


def target_file(name):
    return any(name.startswith(prefix) or name.startswith(prefix[:-1] + ".") for prefix in PREFIXES)


def target_fieldmap(name):
    return any(name.startswith(f"sub-11935_ses-01_acq-{task}_run-1_") for task in TASKS)


def filter_spec():
    return {kind: dict(datatype="func", suffix=kind, subject="11935", session="01",
                       task=list(TASKS), run="1", part=[None, "mag"])
            for kind in ("bold", "sbref")}


def prune_conversion(project):
    """Retain unrelated converted files in the workspace, never in production."""
    session = project / "bids/sub-11935/ses-01"
    for folder in (session / "func", session / "fmap"):
        if not folder.exists():
            continue
        for path in sorted(folder.iterdir()):
            keep = target_file(path.name) if folder.name == "func" else target_fieldmap(path.name)
            require(path.is_file() and not path.is_symlink(), "Unexpected converted directory/symlink")
            if not keep:
                destination = project / "converted-not-promoted" / path.relative_to(project)
                destination.parent.mkdir(parents=True, exist_ok=True)
                require(not destination.exists(), "Unrelated converted-file archive already exists")
                path.rename(destination)
    # The installer merges these rows with unrelated canonical acquisition rows.
    scans = session / "sub-11935_ses-01_scans.tsv"
    if scans.exists():
        frame = pd.read_csv(scans, sep="\t", dtype=str, keep_default_na=False)
        require("filename" in frame, "Converted scans table lacks filename")
        keep = frame.filename.map(lambda x: target_file(Path(x).name))
        frame.loc[keep].to_csv(scans, sep="\t", index=False)
    reviewed.validate_bids(project, "11935")


def container_args(args, destination):
    return SimpleNamespace(project=destination, image=args.image,
                           templateflow=args.templateflow, licenses=args.licenses)


def stage_patch(args, destination):
    probe = ("import json,importlib.metadata as m;import niworkflows.func.util as u;"
             "from pathlib import Path;print(json.dumps(dict(module=str(Path(u.__file__).resolve()),"
             "source=Path(u.__file__).read_text(),fmriprep=m.version('fmriprep'),"
             "niworkflows=m.version('niworkflows'))))")
    command = initialization.container_base(container_args(args, destination), destination)
    raw = subprocess.check_output([*command, str(args.image), "python", "-c", probe], text=True)
    info = json.loads(raw)
    require((info["fmriprep"], info["niworkflows"]) == ("25.2.5", "1.14.4"),
            "This targeted repair requires the tested 25.2.5/1.14.4 container")
    folder = destination / "patch"
    folder.mkdir(exist_ok=True)
    original, patched = folder / "original_util.py", folder / "util.py"
    expected = initialization.patch_source(info["source"])
    if original.exists() or patched.exists():
        require(original.is_file() and patched.is_file() and original.read_text() == info["source"]
                and patched.read_text() == expected, "Existing patch differs; preserve this workspace")
    else:
        original.write_text(info["source"])
        patched.write_text(expected)
    require(initialization.sha(original) == ORIGINAL_UTIL_SHA, "Installed source differs from paired tests")
    result = dict(installed_module=info["module"], fmriprep="25.2.5", niworkflows="1.14.4",
                  original_sha256=initialization.sha(original), patched_sha256=initialization.sha(patched),
                  upstream=initialization.PATCH_URL, change="init_aff Affine -> Rigid only",
                  image=str(args.image), image_sha256=initialization.sha(args.image),
                  master_seed=initialization.FULL_SEED, omp_threads=1)
    write_json(folder / "provenance.json", result)
    return result


def fmriprep_command(args, destination, module_path):
    command = initialization.container_base(container_args(args, destination), destination)
    return [*command, "--bind", f"{destination}/patch/util.py:{module_path}:ro", str(args.image),
            "fmriprep", "/project/bids", "/out/derivatives/fmriprep", "participant",
            "--participant-label", "11935", "--session-label", "01",
            "--bids-filter-file", "/out/filter.json", "--derivatives", "anatomy=/out/anatomy",
            "--fs-subjects-dir", "/out/derivatives/freesurfer", "--fs-no-resume",
            "--fs-license-file", "/licenses/fs_license.txt", "--output-spaces",
            "MNI152NLin6Asym", "T1w", "fsLR", "--cifti-output", "91k", "--me-output-echos",
            "--nprocs", str(args.jobs), "--omp-nthreads", "1", "--mem", "32000",
            "--random-seed", str(initialization.FULL_SEED), "--stop-on-first-crash", "--notrack",
            "--skip-bids-validation", "-w", "/out/functional-cache"]


def stage_freesurfer(production, destination, build):
    """Copy completed anatomy under its real subject ID; never run recon-all."""
    root = production / "derivatives/freesurfer"
    candidates = [root / name for name in ("sub-11935", "sub-11935_ses-01")
                  if (root / name).is_dir()]
    require(len(candidates) == 1, "Need exactly one existing 11935 FreeSurfer subject directory")
    source = candidates[0]
    require(not source.is_symlink(), "FreeSurfer source directory cannot be a symlink")
    required = ["scripts/recon-all.done", "mri/aparc+aseg.mgz", "mri/brain.mgz",
                *[f"surf/{hemi}.{surface}" for hemi in ("lh", "rh")
                  for surface in ("white", "pial", "sphere.reg")]]
    require(all((source / name).is_file() for name in required), "Complete FreeSurfer source required; no anatomy rerun")
    require(not list((source / "scripts").glob("IsRunning*")), "FreeSurfer source has an IsRunning marker; inspect before copying")
    paths = sorted(source.rglob("*"))
    require(not any(p.is_symlink() and not p.is_file() for p in paths),
            "FreeSurfer source contains directory or broken symlinks; inspect before copying")
    files = {str(p.relative_to(source)): initialization.sha(p) for p in paths if p.is_file()}
    record = destination / "freesurfer-copy.json"
    expected = dict(source=str(source), subject_id=source.name, files=files)
    if record.exists():
        saved = json.loads(record.read_text())
        require(all(saved.get(k) == v for k, v in expected.items()), "FreeSurfer source changed since copy receipt")
    else:
        require(build, "FreeSurfer copy receipt missing; run build to stage verified existing anatomy")
        write_json(record, dict(**expected, validated=False))
    target = destination / "derivatives/freesurfer" / source.name
    require(target.resolve() == target, "FreeSurfer copy destination cannot contain a symlink")
    alternative = target.parent / ("sub-11935" if source.name.endswith("_ses-01") else "sub-11935_ses-01")
    require(not alternative.exists() and not alternative.is_symlink(), "Conflicting staged FreeSurfer subject ID")
    copied = 0
    for name, digest in files.items():
        path = target / name
        require(path.resolve() == path, "Staged FreeSurfer file cannot contain a symlink")
        if path.exists():
            require(path.is_file() and initialization.sha(path) == digest, "Existing FreeSurfer copy differs; refusing overwrite")
            continue
        require(build, "FreeSurfer copy incomplete; no anatomy rerun")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".rf1-copy-tmp")
        require(not temporary.is_symlink(), "FreeSurfer copy temporary cannot be a symlink")
        # A previous interrupted copy can leave only this unpublished temporary.
        if temporary.exists():
            temporary.unlink()
        reviewed.copy_shared_file(source / name, temporary)
        require(initialization.sha(temporary) == digest, "FreeSurfer source changed during copy")
        os.replace(temporary, path)
        copied += 1
    require(files == {str(p.relative_to(source)): initialization.sha(p)
                      for p in sorted(source.rglob("*")) if p.is_file()}, "FreeSurfer source changed during staging")
    require(all(initialization.sha(target / name) == digest for name, digest in files.items()), "FreeSurfer copy verification failed")
    if build and (copied or not json.loads(record.read_text()).get("validated")):
        write_json(record, dict(**expected, validated=True))
    print(f"FREESURFER VERIFIED: {source.name}; {len(files)} files; {copied} copied, remainder unchanged; no anatomy processing", flush=True)
    return target


def validate_functional(project, production, report):
    reviewed.validate_bids(project, "11935")
    func = project / "derivatives/fmriprep/sub-11935/ses-01/func"
    require(func.is_dir(), "No repaired functional outputs")
    require(all(target_file(p.name) for p in func.iterdir()), "Unexpected functional run in repair outputs")
    report.mkdir(parents=True, exist_ok=True)
    original_mni = initialization.one(production / "derivatives/fmriprep/sub-11935/ses-01/func",
        "sub-11935_ses-01_task-socialdoors_run-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz")
    original_grid = nib.load(original_mni)
    result = {}
    for task in TASKS:
        stem = f"sub-11935_ses-01_task-{task}_run-1"
        echoes = [func / f"{stem}_echo-{echo}_part-mag_desc-preproc_bold.nii.gz" for echo in range(1, 5)]
        reference = initialization.check_volume(echoes[0], 218)
        for path in echoes[1:]:
            image = initialization.check_volume(path, 218)
            require(image.shape == reference.shape and np.allclose(image.affine, reference.affine),
                    "Preprocessed echoes differ in geometry")
        mni = func / f"{stem}_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"
        image = initialization.check_volume(mni, 218)
        require(image.shape[:3] == original_grid.shape[:3] and np.allclose(image.affine, original_grid.affine),
                "Repaired MNI grid differs from canonical grid")
        q, qcode = image.get_qform(coded=True)
        s, scode = image.get_sform(coded=True)
        require(qcode and scode and np.allclose(q, s, atol=1e-4), "MNI qform/sform inconsistent")
        frame = pd.read_csv(func / f"{stem}_part-mag_desc-confounds_timeseries.tsv", sep="\t")
        required = {"trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z", "framewise_displacement"}
        require(len(frame) == 218 and required <= set(frame), "Repaired motion/confound alignment failed")
        require(np.isfinite(frame[list(required)].iloc[1:].to_numpy(float)).all(), "Nonfinite motion confounds")
        cifti = initialization.one(func, f"{stem}*_space-fsLR_den-91k_bold.dtseries.nii")
        cifti_image = nib.load(cifti)
        require(len(cifti_image.shape) == 2 and cifti_image.shape[0] == 218 and
                np.isfinite(np.asarray(cifti_image.dataobj)).all(), "Invalid repaired CIFTI time series")
        native_mask = func / f"{stem}_part-mag_desc-brain_mask.nii.gz"
        coreg = func / f"{stem}_part-mag_desc-coreg_boldref.nii.gz"
        sources = json.loads(coreg.with_name(coreg.name.replace(".nii.gz", ".json")).read_text())["Sources"]
        require(any(f"{stem}_echo-1_sbref.nii.gz" in x for x in sources) and
                any(f"acq-{task}_run-1_" in x and "desc-coeff_fieldmap" in x for x in sources),
                "Functional reference does not identify its matched SBRef/fieldmap")
        for source in sources:
            if source.startswith("bids::"):
                require((project / "derivatives/fmriprep" / source.removeprefix("bids::")).is_file(),
                        "Functional reference points to a missing derivative source")
        mask = func / f"{stem}_part-mag_space-MNI152NLin6Asym_desc-brain_mask.nii.gz"
        coverage = compute_coverage(production / TARGET, mask)
        require(np.isfinite(coverage), "Nonfinite repaired coverage")
        montage(nib.load(coreg), report / f"{task}-native.png", f"11935 corrected {task}: native",
                mask=nib.load(native_mask))
        mean = np.asarray(image.dataobj, dtype=np.float32).mean(axis=3)
        montage(nib.Nifti1Image(mean, image.affine), report / f"{task}-MNI.png",
                f"11935 corrected {task}: MNI mean", target=nib.load(production / TARGET),
                mask=nib.load(mask), fixed_mni=True)
        result[task] = dict(volumes=218, confound_rows=218, canonical_coverage_pct=coverage,
                            motion_reestimated=True, source_series=25 if task == "socialdoors" else 29,
                            sbref_series=23 if task == "socialdoors" else 27)
    commands = [p for p in (project / "functional-cache").rglob("command.txt")
                if "init_aff" in p.parts and "enhance_and_skullstrip_bold_wf" in p.parts]
    require(len(commands) == 2 and all("Rigid[0.1]" in p.read_text() for p in commands),
            "Both corrected full runs must demonstrate actual Rigid initialization")
    write_json(report / "functional-validation.json", result)
    return result


def publishable_files(project):
    allowed = []
    for root in ("bids/sub-11935/ses-01/func", "derivatives/fmriprep/sub-11935/ses-01/func",
                 "derivatives/fmriprep/sub-11935/ses-01/fmap",
                 "derivatives/fmriprep/sub-11935/figures", "derivatives/mriqc/sub-11935/ses-01/func",
                 "derivatives/fmriprep/sub-11935/ses-01/figures", "derivatives/mriqc/sub-11935/ses-01/figures",
                 "derivatives/warpkit/sub-11935/ses-01", "derivatives/tedana/sub-11935/ses-01",
                 "derivatives/tedana/sub-11935/ses-01/figures",
                 "derivatives/fsl/confounds_tedana/sub-11935", "derivatives/mriqc"):
        folder = project / root
        for path in sorted(folder.glob("*")):
            fieldmap_root = "fmriprep" in root and (root.endswith("/fmap") or root.endswith("/figures"))
            if path.is_file() and (target_file(path.name) or (fieldmap_root and target_fieldmap(path.name))):
                allowed.append(path)
    fmap = project / "bids/sub-11935/ses-01/fmap"
    allowed += [p for p in sorted(fmap.glob("*")) if p.is_file() and target_fieldmap(p.name)]
    require(allowed, "No repair products")
    require(all(not p.is_symlink() for p in allowed), "Repair products cannot be symlinks")
    return {str(p.relative_to(project)): initialization.sha(p) for p in sorted(set(allowed))}


def annotate_derivatives(project, patch):
    for path in (project / "derivatives/fmriprep/sub-11935/ses-01/func").glob("*.json"):
        if not target_file(path.name):
            continue
        metadata = json.loads(path.read_text())
        record = dict(fmriprep="25.2.5", upstream_patch=initialization.PATCH_URL,
                      patched_module_sha256=patch["patched_sha256"], image_sha256=patch["image_sha256"],
                      master_seed=initialization.FULL_SEED,
                      source_mapping="PI-approved Faces 25/26 with SBRef23; Doors 29/30 with SBRef27")
        if metadata.get("RF1Repair") != record:
            require("RF1Repair" not in metadata, "Existing derivative repair provenance differs")
            metadata["RF1Repair"] = record
            write_json(path, metadata)


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield stream


def run(args):
    production, work = args.project_root.resolve(), args.work_dir.resolve()
    require(work.is_relative_to(production / "work") and not work.is_symlink(), "Workspace must be under work/")
    require(args.exclusions_root.is_dir() and not (args.exclusions_root / "Smith-SRA-11935").exists(),
            "Source-exclusion root missing or 11935 source-excluded")
    reviewed.behavior_preflight(args.behavior_root, "11935")
    initialization.anat_files(production)
    for path in (args.image, args.licenses / "fs_license.txt", production / TARGET):
        require(path.is_file(), f"Missing prerequisite: {path}")
    if args.command == "plan":
        print("11935 only: corrected Faces 25/26 + SBRef23; Doors29/30 + SBRef27.")
        print("Fresh two-run functional processing on 25.2.5 + tested Rigid backport; reuse anatomy/FreeSurfer.")
        print("Rebuild WarpKit, MRIQC, motion/SDC/registration/resampling/confounds, production TEDANA.")
        print("Stage only. Promotion, cohort input revision, task models and QC refresh are separate checked steps.")
        return
    work.mkdir(parents=True, exist_ok=True)
    with locked(work / ".stage.lock") as lock:
        destination = work / "sub-11935-project"
        path = destination / "repair.json"
        if not path.exists():
            require(args.command == "build", "No staged repair exists")
            receipt = reviewed.initialize(production, destination, "11935")
        else:
            receipt = json.loads(path.read_text())
        require(receipt.get("state") == "ready" and receipt["production"] == str(production), "Invalid stage receipt")
        runner_sha = initialization.sha(Path(__file__))
        if "completion_runner_sha256" not in receipt:
            require(args.command == "build", "Completion-runner receipt missing")
            receipt["completion_runner_sha256"] = runner_sha
            write_json(path, receipt)
        require(receipt["completion_runner_sha256"] == runner_sha, "Completion runner changed; use a new workspace")
        require(receipt["code"] == reviewed.code_hashes(destination / "code", receipt["code"]), "Staged pipeline code changed")
        require(receipt["protected"] == reviewed.signatures(reviewed.protected_paths(production, "11935")),
                "Production inputs changed; inspect staged repair before continuing")
        ready = destination / "11935-ready.json"
        if ready.exists():
            old = json.loads(ready.read_text())
            require(old["files"] == publishable_files(destination), "Previously validated staged products changed")
        env = {**os.environ, "BEHAVIOR_ROOT": str(args.behavior_root), "SOURCEDATA_ROOT": str(args.source_root),
               "SOURCEDATA_EXCLUSIONS_ROOT": str(args.exclusions_root), "SCRATCH_ROOT": str(destination / "scratch"),
               "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
               "PYTHONUNBUFFERED": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
               "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "MRIQC_NPROCS": "4", "MRIQC_MEM_GB": "16"}

        def execute(command):
            print("COMMAND: " + " ".join(map(str, command)), flush=True)
            subprocess.run(list(map(str, command)), cwd=destination, env=env, check=True, pass_fds=(lock.fileno(),))

        def step(name, command, check):
            marker = destination / "completion-stages" / f"{name}.json"
            if args.command == "build" and not marker.exists():
                execute(command)
                check()
                write_json(marker, {"passed": True})
            else:
                require(marker.exists(), f"Stage not complete: {name}")
                check()

        sublist = str(destination / "subject.txt")
        py = sys.executable
        converted = destination / "bids/sub-11935/ses-01"
        if not converted.exists():
            require(args.command == "build", "No converted session")
            execute(["bash", "code/prepdata.sh", "11935", "01"])
        if not (destination / "completion-stages/pruned.json").exists():
            require(args.command == "build", "Converted input pruning not complete")
            prune_conversion(destination)
            write_json(destination / "completion-stages/pruned.json", {"passed": True})
        reviewed.validate_bids(destination, "11935")
        execute([py, "code/check_events.py", "--subject", "11935", "--session", "01", "--behavior-root", args.behavior_root, "--quiet-ok"])
        step("warpkit", ["bash", "code/run_warpkit.sh", "--sublist", sublist, "--jobs", "2"],
             lambda: execute(["bash", "code/check_warpkit.sh", "--sublist", sublist]))
        if args.command == "build":
            execute([py, "code/addIntendedFor.py", "--sublist", sublist])
        step("mriqc", ["bash", "code/mriqc.sh", "11935", "01"], lambda: reviewed.validate_mriqc(destination, "11935"))
        anatomy = destination / "anatomy"
        for source in initialization.anat_files(production):
            target = anatomy / source.relative_to(production / "derivatives/fmriprep")
            if not target.exists():
                require(args.command == "build", "Anatomy copy missing")
                target.parent.mkdir(parents=True, exist_ok=True)
                reviewed.copy_shared_file(source, target)
            require(initialization.sha(source) == initialization.sha(target), "Anatomy copy differs from preserved source")
        for source in sorted((production / "derivatives/freesurfer").glob("fsaverage*")):
            target = destination / "derivatives/freesurfer" / source.name
            if source.is_dir() and not target.exists():
                require(args.command == "build", "FreeSurfer reference copy missing")
                reviewed.copy_shared_tree(source.resolve(), target)
        stage_freesurfer(production, destination, args.command == "build")
        write_json(destination / "filter.json", filter_spec())
        patch = stage_patch(args, destination)
        step("fmriprep", fmriprep_command(args, destination, patch["installed_module"]),
             lambda: execute(["bash", "code/check_fmriprep.sh", "--sublist", sublist]))
        geometry = destination / "logs/geometry/11935-repaired"
        reviewed.check_geometry(destination, geometry, execute)
        functional = validate_functional(destination, production, work / "review")
        step("tedana", ["bash", "code/run_tedana.sh", "--sublist", sublist, "--session", "01", "--jobs", "1"],
             lambda: execute(["bash", "code/check_tedana.sh", "--sublist", sublist, "--session", "01", "--expected-runs", "2"]))
        if args.command == "build":
            execute([py, "code/genTedanaConfounds.py", "--sublist", sublist, "--session", "01", "--preserve-existing"])
        execute([py, "code/genTedanaConfounds.py", "--sublist", sublist, "--session", "01", "--check"])
        annotate_derivatives(destination, patch)
        require(receipt["protected"] == reviewed.signatures(reviewed.protected_paths(production, "11935")),
                "Production changed during staging; do not promote")
        write_json(ready, dict(validated=True, subject="11935", session="01", tasks=list(TASKS),
                   files=publishable_files(destination), patch=patch, functional=functional,
                   production_modified=False, scientific_acceptance=False, inputs=receipt["protected"]))
        with tarfile.open(work / "11935-repair-review.tar.gz", "w:gz") as archive:
            archive.add(work / "review", arcname="11935-repair-review")
        print("CHECK PASSED: both corrected 11935 runs staged through TEDANA/confounds; production unchanged.")
        print(f"Inspect native/MNI montages: {work / 'review'}")


def main():
    os.umask(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "build", "check"))
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--behavior-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra/stimuli"))
    parser.add_argument("--source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra"))
    parser.add_argument("--exclusions-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    parser.add_argument("--image", type=Path, default=Path("/ZPOOL/data/tools/fmriprep-25.2.5.simg"))
    parser.add_argument("--templateflow", type=Path, default=Path("/ZPOOL/data/tools/templateflow"))
    parser.add_argument("--licenses", type=Path, default=Path("/ZPOOL/data/tools/licenses"))
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    try:
        require(1 <= args.jobs <= 16, "Use 1-16 workers for this two-run repair")
        run(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
