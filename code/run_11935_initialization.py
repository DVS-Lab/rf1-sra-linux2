#!/usr/bin/env python3
"""Compare original/rigid BOLD-mask initialization with isolated 11935 outputs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import importlib.metadata
import json
import os
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import sys
import tarfile
import traceback

STEM = "sub-11935_ses-01_task-socialdoors_run-1"
CONTROL = "sub-11935_ses-01_task-ugr_run-1"
VERSION = "25.2.5"
SEEDS = (20261021, 20261022, 20261023, 20261024, 20261025)
FULL_SEED = SEEDS[0]  # Prespecified, never selected by the best-looking reference.
TARGET = "rf1-sra_MNI152NLin6Asym_desc-qctarget_mask.nii.gz"
OLD = "transform=('Affine', 0.1),"
NEW = "transform=('Rigid', 0.1),"
PATCH_URL = "https://github.com/nipreps/niworkflows/pull/1064"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def inventory(project):
    raw = project / "bids/sub-11935/ses-01/func"
    func = project / "derivatives/fmriprep/sub-11935/ses-01/func"
    images = {}
    for echo in range(1, 5):
        for stem, label in ((STEM, "sbref"), (CONTROL, "control_sbref")):
            # The actual BIDS SBRefs have no part entity, unlike the BOLD derivatives.
            source = raw / f"{stem}_echo-{echo}_sbref.nii.gz"
            if source.is_file():
                images[f"{label}_echo{echo}"] = source
            elif label == "sbref" or echo == 1:
                raise ValueError(f"Required SBRef missing: {source.name}")
    for stem, prefix in ((STEM, "production"), (CONTROL, "control")):
        for label, suffix in (("hmc", "desc-hmc_boldref"), ("coreg", "desc-coreg_boldref"),
                              ("mask", "desc-brain_mask")):
            source = func / f"{stem}_part-mag_{suffix}.nii.gz"
            if not source.is_file():
                raise ValueError(f"Required reference/mask missing: {source.name}")
            images[f"{prefix}_{label}"] = source
    return images


def patch_source(source):
    # Restrict the one-line backport to the named workflow, not other registrations.
    start = source.index("def init_enhance_and_skullstrip_bold_wf(")
    end = source.find("\ndef ", start + 1)
    end = len(source) if end < 0 else end
    function = source[start:end]
    if function.count(OLD) != 1 or NEW in function or "name='init_aff'" not in function:
        raise ValueError("Installed workflow differs from the expected upstream patch context")
    return source[:start] + function.replace(OLD, NEW) + source[end:]


def bids_filter():
    return {kind: dict(datatype="func", suffix=kind, subject="11935", session="01",
                       task="socialdoors", run=1, part=[None, "mag"])
            for kind in ("bold", "sbref")}


def anat_files(project):
    root = project / "derivatives/fmriprep"
    files = [root / "dataset_description.json"]
    subject = root / "sub-11935"
    for folder in (subject / "anat", subject / "ses-01/anat"):
        if folder.is_dir():
            files.extend(p for p in sorted(folder.rglob("*")) if p.is_file())
    names = [p.name for p in files]
    required = ("desc-preproc_T1w.nii.gz", "desc-brain_mask.nii.gz", "dseg.nii.gz",
                "from-T1w_to-MNI152NLin6Asym_mode-image_xfm.h5",
                "from-MNI152NLin6Asym_to-T1w_mode-image_xfm.h5")
    for suffix in required:
        if not any(name.endswith(suffix) for name in names):
            raise ValueError("Missing reusable anatomical derivative: " + suffix)
    if not files[0].is_file():
        raise ValueError("Missing anatomical derivative dataset description")
    return files


def full_command(args, output, mode, module_path):
    cmd = container_base(args, output)
    if mode == "rigid":
        cmd += ["--bind", f"{output}/patch/util.py:{module_path}:ro"]
    # Same processing in both conditions; omit CIFTI/surface resampling only.
    cmd += [str(args.image.resolve()), "fmriprep", "/project/bids", f"/out/full/{mode}/derivatives",
            "participant", "--participant-label", "11935", "--session-label", "01",
            "--task-id", "socialdoors", "--bids-filter-file", "/out/filter.json",
            "--derivatives", "anatomy=/out/anatomy", "--fs-subjects-dir", f"/out/fs/{mode}",
            "--fs-no-resume", "--fs-license-file", "/licenses/fs_license.txt",
            "--output-spaces", "MNI152NLin6Asym", "T1w", "--me-output-echos",
            "--nprocs", str(args.nprocs), "--omp-nthreads", "1", "--mem", "24000",
            "--random-seed", str(FULL_SEED), "--stop-on-first-crash", "--notrack",
            "--skip-bids-validation", "-w", f"/out/full/{mode}/cache"]
    return cmd


def container_base(args, output):
    return ["apptainer", "exec", "--cleanenv", "--containall", "--no-mount",
            "cwd,home,hostfs,bind-paths", "--bind", f"{args.project.resolve()}:/project:ro",
            "--bind", f"{output}:/out:rw", "--bind", f"{args.templateflow.resolve()}:/opt/templateflow:ro",
            "--bind", f"{args.licenses.resolve()}:/licenses:ro", "--pwd", "/out",
            "--env", "TEMPLATEFLOW_HOME=/opt/templateflow", "--env", "HOME=/out/home",
            "--env", "MPLCONFIGDIR=/out/.mpl", "--env", "OMP_NUM_THREADS=1",
            "--env", "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=1", "--env", "OPENBLAS_NUM_THREADS=1",
            "--env", "MKL_NUM_THREADS=1", "--env", "NUMEXPR_NUM_THREADS=1",
            "--env", "PYTHONUNBUFFERED=1", "--env", "PYTHONDONTWRITEBYTECODE=1"]


def run_command(cmd, output, name):
    write_json(output / (name + "-command.json"), cmd)
    print("COMMAND " + name + ": " + shlex.join(cmd), flush=True)
    # Stream into the outer run_logged/nohup log; no hidden child shell or detached jobs.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("APPTAINER_BIND", "SINGULARITY_BIND"))}
    completed = subprocess.run(cmd, cwd=output, env=env, check=False)
    if completed.returncode:
        raise RuntimeError(f"{name} exited {completed.returncode}; isolated outputs retained")


def signatures(paths):
    return {str(p): dict(size=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns)
            for p in paths}


def guard_output(project, output):
    if project / "work" not in output.parents:
        raise ValueError("Output must be a NEW directory under PROJECT/work")
    if output.exists() or output.with_suffix(".tar.gz").exists():
        raise ValueError("Output/archive exists; use a new timestamp (never overwrite)")


def host(args):
    args.project = args.project.resolve()
    output = args.output.resolve()
    guard_output(args.project, output)
    if not 1 <= args.nprocs <= 16:
        raise ValueError("Use 1-16 total full-run processes; OMP stays at one")
    images = inventory(args.project)
    anatomy = anat_files(args.project)
    fsroot = args.project / "derivatives/freesurfer"
    fs_subjects = [p for p in (fsroot / "sub-11935", fsroot / "sub-11935_ses-01") if p.is_dir()]
    if not fs_subjects or not (args.licenses / "fs_license.txt").is_file():
        raise ValueError("Need existing FreeSurfer subject and license")
    if not args.image.is_file() or not args.templateflow.is_dir() or not shutil.which("apptainer"):
        raise ValueError("Need existing image, TemplateFlow cache and apptainer")
    print("PLAN: five paired seeds, ten sequential pre-SDC tests, then two sequential full functional runs.")
    print("Original and one-line rigid backport; fixed full-run seed; no production changes.")
    print("Anatomy-only reuse: %d files. Full functional cache reuse: NONE." % len(anatomy))
    if args.dry_run:
        print("DRY RUN: no files changed. Container/version/input checks also run at launch.")
        return 0
    output.mkdir(parents=True)
    for name in ("inputs", "patch", "evidence", "home", ".mpl"):
        (output / name).mkdir()
    shutil.copyfile(Path(__file__), output / "run_11935_initialization.py")
    write_json(output / "filter.json", bids_filter())
    records = []
    for label, path in images.items():
        destination = output / "inputs" / (label + ".nii.gz")
        digest = sha(path)
        shutil.copyfile(path, destination)
        if digest != sha(destination):
            raise ValueError("Source changed during copy")
        records.append(dict(label=label, source=str(path), copied=str(destination.relative_to(output)), sha256=digest))
    write_json(output / "inputs.json", records)
    # Copy, never hardlink or symlink, reusable anatomy. No fmap/func cache is staged.
    for source in anatomy:
        destination = output / "anatomy" / source.relative_to(args.project / "derivatives/fmriprep")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        if sha(source) != sha(destination):
            raise ValueError("Anatomical input changed during copy")
    for mode in ("affine", "rigid"):
        print("Staging independent FreeSurfer copy: " + mode, flush=True)
        (output / "fs" / mode).mkdir(parents=True)
        for source in fs_subjects + sorted(fsroot.glob("fsaverage*")):
            if source.is_dir():
                shutil.copytree(source, output / "fs" / mode / source.name, symlinks=False)
    # Snapshot subject BIDS/derivatives + production FreeSurfer metadata; all container inputs are RO.
    protected = set(anatomy) | set(images.values())
    for base in (args.project / "bids/sub-11935", args.project / "derivatives/fmriprep/sub-11935"):
        protected.update(p for p in base.rglob("*") if p.is_file())
    for base in fs_subjects:
        protected.update(p for p in base.rglob("*") if p.is_file())
    before = signatures(sorted(protected))
    write_json(output / "protected-input-signatures.json", before)
    state = dict(status="running", validated=False, seeds=list(SEEDS), full_seed=FULL_SEED,
                 production_replacement=False, patch=PATCH_URL)
    write_json(output / "state.json", state)
    error = None
    try:
        base = container_base(args, output)
        run_command(base + [str(args.image.resolve()), "python", "/out/run_11935_initialization.py",
                            "--inside", "pairs"], output, "paired-references")
        patch = json.loads((output / "patch/provenance.json").read_text())
        failures = []
        for mode in ("affine", "rigid"):
            try:
                run_command(full_command(args, output, mode, patch["installed_module"]), output, "full-" + mode)
                run_command(base + [str(args.image.resolve()), "python", "/out/run_11935_initialization.py",
                                    "--inside", "validate", "--mode", mode], output, "validate-" + mode)
            except RuntimeError as exc:
                # Failure of the original condition is itself experimental evidence;
                # still test the patched condition, without sharing either cache.
                failures.append(dict(mode=mode, error=str(exc)))
                print("FAILED CONDITION " + mode + ": " + str(exc), flush=True)
        if failures:
            write_json(output / "full-condition-failures.json", failures)
            raise RuntimeError("One or more full-run conditions failed; inspect experiment comparison")
        state.update(status="technical_checks_passed", validated=True,
                     interpretation="Inspect paired images and full-run reports before scientific acceptance.")
    except BaseException as exc:
        error = exc
        state.update(status="failed_or_interrupted", error_type=type(exc).__name__, error=str(exc))
        (output / "error.txt").write_text(traceback.format_exc())
    finally:
        state["production_inputs_unchanged"] = before == signatures(sorted(protected))
        state["reference_hashes_unchanged"] = all(sha(r["source"]) == r["sha256"] for r in records)
        if not state["production_inputs_unchanged"] or not state["reference_hashes_unchanged"]:
            state.update(status="failed_source_change", validated=False)
        write_json(output / "state.json", state)
        make_report(output)
        # Export evidence only. Full 4D BOLD, FreeSurfer, anatomy and cache stay on Linux2.
        members = [p for p in sorted(output.iterdir())
                   if p.is_file() or p.name in {"inputs", "patch", "evidence", "pairs"}]
        with tarfile.open(output.with_suffix(".tar.gz"), "w:gz") as archive:
            for path in members:
                archive.add(path, arcname=output.name + "/" + path.name)
        print("Experiment results/archive: " + str(output), flush=True)
        print(str(output.with_suffix(".tar.gz")), flush=True)
    if error:
        raise error
    if not state["validated"]:
        raise ValueError("Production input preservation check failed")
    print("CHECK PASSED: paired tests/full-run integrity and input preservation. Visual/scientific review remains.")
    return 0


def graph_output(graph, name):
    nodes = [node for node in graph.nodes if node.name == name]
    if len(nodes) != 1:
        raise ValueError("Executed node not unique: " + name)
    return nodes[0].result.outputs


def check_volume(path, expected=None):
    import nibabel as nib
    import numpy as np
    img = nib.load(path)
    if expected is not None and (len(img.shape) != 4 or img.shape[3] != expected):
        raise ValueError("Wrong BOLD volume count: " + str(path))
    if len(img.shape) not in (3, 4) or not np.isfinite(img.affine).all():
        raise ValueError("Invalid dimensions/affine: " + str(path))
    # Read gzip once; repeated proxy slicing can repeatedly decompress the entire series.
    data = np.asarray(img.dataobj)
    if not np.isfinite(data).all():
        raise ValueError("Nonfinite voxels: " + str(path))
    if not np.any(data != 0):
        raise ValueError("Empty image: " + str(path))
    return img


def paired_tests():
    import nibabel as nib
    import numpy as np
    import niworkflows.func.util as util
    from nipype import config, Node
    from nipype.interfaces.io import DataSink
    from nibabel.processing import resample_from_to
    sys.path.insert(0, "/project/code")
    from inspect_xa60_coverage import montage

    root = Path("/out")
    versions = {p: importlib.metadata.version(p) for p in ("fmriprep", "niworkflows", "nipype", "smriprep")}
    if versions["fmriprep"] != VERSION or versions["niworkflows"] != "1.14.4":
        raise ValueError("Unexpected fMRIPrep/niworkflows version; do not silently adapt experiment")
    original = Path(util.__file__).resolve()
    source = original.read_text()
    patched = patch_source(source)
    (root / "patch/original_util.py").write_text(source)
    (root / "patch/util.py").write_text(patched)
    write_json(root / "patch/provenance.json", dict(installed_module=str(original), versions=versions,
               original_sha256=sha(original), patched_sha256=sha(root / "patch/util.py"), url=PATCH_URL,
               change="init_aff only: Affine[0.1] -> Rigid[0.1]; norm unchanged",
               threads=1, seed_scope="ANTS_RANDOM_SEED; single-threaded ANTs; no original historical seed available"))
    from smriprep.utils.bids import collect_derivatives
    cache = collect_derivatives(derivatives_dir="/out/anatomy", subject_id="11935",
                               std_spaces=["MNI152NLin6Asym", "fsnative"])
    required = {"t1w_preproc", "t1w_mask", "t1w_dseg", "t1w_tpms"}
    if not required.issubset(cache):
        raise ValueError("Anatomy-only cache is incomplete: " + str(sorted(required - cache.keys())))
    for space in ("MNI152NLin6Asym", "fsnative"):
        if not {"forward", "reverse"}.issubset(cache.get("transforms", {}).get(space, {})):
            raise ValueError("Missing precomputed bidirectional anatomical transform: " + space)
    write_json(root / "anatomy-cache.json", cache)
    config.update_config({"execution": {"remove_unnecessary_outputs": False,
                                        "stop_on_first_crash": True, "crashfile_format": "txt"}})
    image = check_volume(root / "inputs/sbref_echo1.nii.gz")
    if len(image.shape) != 3:
        raise ValueError("Expected the previously inspected 3D original echo-1 SBRef")
    for echo in range(1, 5):
        path = Path("/project/bids/sub-11935/ses-01/func") / (STEM + f"_echo-{echo}_sbref.json")
        metadata = json.loads(path.read_text())
        if echo == 1:
            previous = 0
        current = metadata["EchoTime"]
        if not previous < current or metadata["RepetitionTime"] != 1.615:
            raise ValueError("SBRef echo order/TR differs from inspected acquisition")
        previous = current
    production = nib.load(root / "inputs/production_mask.nii.gz")
    rows = []
    for index, seed in enumerate(SEEDS):
        for mode in (("affine", "rigid") if index % 2 == 0 else ("rigid", "affine")):
            os.environ["ANTS_RANDOM_SEED"] = str(seed)
            random.seed(seed)
            np.random.seed(seed)
            label = f"seed_{seed}_{mode}"
            print("STARTED " + label, flush=True)
            wf = util.init_enhance_and_skullstrip_bold_wf(name=label, omp_nthreads=1)
            if tuple(wf.get_node("init_aff").inputs.transform) != ("Affine", 0.1):
                raise ValueError("Original init_aff node is not Affine[0.1]")
            if mode == "rigid":
                wf.get_node("init_aff").inputs.transform = ("Rigid", 0.1)
            wf.base_dir = "/out/pair_cache"
            wf.config.setdefault("execution", {})["remove_unnecessary_outputs"] = False
            wf.inputs.inputnode.in_file = "/out/inputs/sbref_echo1.nii.gz"
            wf.get_node("n4_correct").inputs.save_bias = True
            sink = Node(DataSink(base_directory=f"/out/pairs/{label}", parameterization=False), name="retain_bias")
            wf.connect(wf.get_node("n4_correct"), "bias_image", sink, "@bias")
            graph = wf.run(plugin="Linear")
            dest = root / "pairs" / label
            dest.mkdir(parents=True, exist_ok=True)
            exports = dict(enhanced=graph_output(graph, "n4_correct").output_image,
                           bias=graph_output(graph, "n4_correct").bias_image,
                           mask=graph_output(graph, "combine_masks").out_file,
                           prior=graph_output(graph, "fix_header").out_file,
                           initialization=graph_output(graph, "init_aff").output_transform)
            for kind, path in exports.items():
                suffix = ".mat" if kind == "initialization" else ".nii.gz"
                shutil.copyfile(path, dest / (kind + suffix))
                if suffix != ".mat":
                    check_volume(dest / (kind + suffix))
            for node in ("init_aff", "norm", "n4_correct"):
                for path in (root / "pair_cache" / label / node).rglob("*"):
                    if path.is_file() and (path.name in {"command.txt", "report.rst"} or path.suffix == ".mat"):
                        target = dest / node / path.relative_to(root / "pair_cache" / label / node)
                        target.parent.mkdir(exist_ok=True, parents=True)
                        shutil.copyfile(path, target)
            mask = nib.load(dest / "mask.nii.gz")
            old = np.asarray(resample_from_to(production, mask, order=0).dataobj) > 0
            current = np.asarray(mask.dataobj) > 0
            row = dict(seed=seed, mode=mode, status="completed", mask_voxels=int(current.sum()),
                       dice_with_production=float(2 * (old & current).sum() / (old.sum() + current.sum())),
                       caution="pre-SDC vs post-SDC production; descriptive comparison, not success threshold")
            rows.append(row)
            for kind in ("enhanced", "bias", "prior"):
                montage(nib.load(dest / (kind + ".nii.gz")), dest / (kind + ".png"),
                        label + " | " + kind, mask=mask if kind == "enhanced" else None)
            montage(image, dest / "input_mask.png", label + " | original SBRef and mask", mask=mask)
            write_json(root / "paired-results.json", rows)
            print("COMPLETED " + label, flush=True)
    if len(rows) != 2 * len(SEEDS):
        raise ValueError("Incomplete seed pairs")
    pairs = []
    for seed in SEEDS:
        a = np.asarray(nib.load(root / "pairs" / f"seed_{seed}_affine/mask.nii.gz").dataobj) > 0
        b = np.asarray(nib.load(root / "pairs" / f"seed_{seed}_rigid/mask.nii.gz").dataobj) > 0
        pairs.append(dict(seed=seed, paired_mask_dice=float(2 * (a & b).sum() / (a.sum() + b.sum()))))
    write_json(root / "paired-comparison.json", pairs)
    stability = {}
    for mode in ("affine", "rigid"):
        masks = [np.asarray(nib.load(root / "pairs" / f"seed_{seed}_{mode}/mask.nii.gz").dataobj) > 0
                 for seed in SEEDS]
        dice = [float(2 * (a & b).sum() / (a.sum() + b.sum()))
                for index, a in enumerate(masks) for b in masks[index + 1:]]
        stability[mode] = dict(min_across_seed_mask_dice=min(dice),
                               mean_across_seed_mask_dice=float(np.mean(dice)),
                               mask_voxel_range=[int(min(m.sum() for m in masks)),
                                                 int(max(m.sum() for m in masks))],
                               caution="Mask repeatability is descriptive, not evidence of anatomical accuracy.")
    write_json(root / "paired-stability.json", stability)
    return 0


def one(folder, pattern):
    paths = sorted(folder.glob(pattern))
    if len(paths) != 1:
        raise ValueError(f"Expected one {pattern}; found {len(paths)}")
    return paths[0]


def validate_full(mode, root=Path("/out"), project=Path("/project")):
    import nibabel as nib
    import numpy as np
    sys.path.insert(0, str(project / "code"))
    import build_run_qc as qc
    from inspect_xa60_coverage import montage

    derivative = root / "full" / mode / "derivatives"
    func = derivative / "sub-11935/ses-01/func"
    if any("task-socialdoors_run-1_" not in p.name for p in func.glob("*bold.nii.gz")):
        raise ValueError("Unexpected other functional run in isolated outputs")
    raw = project / "bids/sub-11935/ses-01/func"
    raw_echoes = []
    for echo in range(1, 5):
        candidates = list(raw.glob(STEM + f"_echo-{echo}*bold.nii.gz"))
        candidates = [p for p in candidates if "_part-phase_" not in p.name]
        if len(candidates) != 1:
            raise ValueError("Raw magnitude echo not unique")
        raw_echoes.append(candidates[0])
    counts = {nib.load(p).shape[3] for p in raw_echoes}
    if len(counts) != 1:
        raise ValueError("Raw echo lengths differ")
    nvol = counts.pop()
    if nvol != 218:
        raise ValueError("Raw run differs from inspected 218-volume acquisition")
    native_echoes = [one(func, STEM + f"_echo-{echo}_part-mag_desc-preproc_bold.nii.gz")
                     for echo in range(1, 5)]
    mni = one(func, STEM + "_part-mag_space-MNI152NLin6Asym*_desc-preproc_bold.nii.gz")
    t1 = one(func, STEM + "_part-mag_space-T1w_desc-preproc_bold.nii.gz")
    checks = []
    for p in native_echoes + [mni, t1]:
        img = check_volume(p, nvol)
        qform, qcode = img.get_qform(coded=True)
        sform, scode = img.get_sform(coded=True)
        # Native inputs can carry scanner conventions, but MNI must have consistent transforms.
        if p == mni and (not qcode or not scode or not np.allclose(qform, sform, atol=1e-4)):
            raise ValueError("MNI qform/sform missing or inconsistent")
        checks.append(dict(path=str(p.relative_to(root)), shape=list(img.shape),
                           orientation=list(nib.aff2axcodes(img.affine)), sha256=sha(p)))
    reference = nib.load(native_echoes[0])
    for p in native_echoes[1:]:
        other = nib.load(p)
        if other.shape != reference.shape or not np.allclose(other.affine, reference.affine, atol=1e-5):
            raise ValueError("Native preprocessed echo grids differ")
    confounds = one(func, STEM + "*_desc-confounds_timeseries.tsv")
    with confounds.open() as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        fields = reader.fieldnames or []
        data = list(reader)
    if len(data) != nvol or not {"trans_x", "trans_y", "trans_z", "framewise_displacement"}.issubset(fields):
        raise ValueError("Confound row count/required fields differ")
    target = project / "qc/reference" / TARGET
    mni_mask = one(func, STEM + "_part-mag_space-MNI152NLin6Asym*_desc-brain_mask.nii.gz")
    native_mask = one(func, STEM + "_part-mag_desc-brain_mask.nii.gz")
    coreg = one(func, STEM + "_part-mag_desc-coreg_boldref.nii.gz")
    coreg_metadata = json.loads(coreg.with_name(coreg.name.replace(".nii.gz", ".json")).read_text())
    sources = coreg_metadata.get("Sources", [])
    if not isinstance(sources, list):
        sources = [sources]
    if not any(STEM + "_echo-1_sbref.nii.gz" in s for s in sources):
        raise ValueError("Full-run reference did not record original echo-1 SBRef")
    if not any("acq-socialdoors_run-1_" in s and "desc-coeff_fieldmap.nii.gz" in s for s in sources):
        raise ValueError("Full-run coreg reference did not record the matched Social Doors fieldmap")
    coverage = qc.compute_coverage(target, mni_mask)
    production_func = project / "derivatives/fmriprep/sub-11935/ses-01/func"
    original_mni = one(production_func, STEM + "_part-mag_space-MNI152NLin6Asym*_desc-preproc_bold.nii.gz")
    original_img, new_img = nib.load(original_mni), nib.load(mni)
    same_grid = original_img.shape[:3] == new_img.shape[:3] and np.allclose(original_img.affine, new_img.affine, atol=1e-4)
    if not same_grid:
        raise ValueError("Full-run MNI grid differs from production grid; do not promote")
    dest = root / "evidence" / mode
    dest.mkdir(exist_ok=True, parents=True)
    for p in sorted(func.glob("*.nii.gz")):
        img = nib.load(p)
        if len(img.shape) == 3:
            check_volume(p)
            shutil.copyfile(p, dest / p.name)
    for p in func.glob("*.json"):
        shutil.copyfile(p, dest / p.name)
    for pattern in ("*xfm.txt", "*xfm.txt.gz"):
        for p in func.glob(pattern):
            shutil.copyfile(p, dest / p.name)
    shutil.copyfile(confounds, dest / confounds.name)
    for p in sorted((derivative / "sub-11935").rglob("*")):
        if p.is_file() and p.suffix in {".svg", ".html", ".toml"}:
            to = dest / "reports" / p.relative_to(derivative / "sub-11935")
            to.parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(p, to)
    subject_report = derivative / "sub-11935.html"
    if subject_report.is_file():
        shutil.copyfile(subject_report, dest / subject_report.name)
    mask_img = check_volume(native_mask)
    montage(check_volume(coreg), dest / "native_postSDC.png", mode + " | post-SDC native reference", mask=mask_img)
    mni_ref = one(func, STEM + "_part-mag_space-MNI152NLin6Asym*_boldref.nii.gz")
    montage(check_volume(mni_ref), dest / "MNI_mask.png", mode + " | full-run MNI reference",
            mask=nib.load(mni_mask), target=nib.load(target), fixed_mni=True)
    # Save spatial mean for review without transferring 4D time series.
    mean = np.asarray(new_img.dataobj, dtype=np.float32).mean(axis=3, dtype=np.float64)
    nib.save(nib.Nifti1Image(mean.astype(np.float32), new_img.affine), dest / "MNI_temporal_mean.nii.gz")
    # Preserve coarse initialization and refinement commands for the actual full workflow.
    cache = root / "full" / mode / "cache"
    nodes = {"init_aff", "norm", "n4_correct", "map_brainmask", "unwarp_boldref"}
    for p in cache.rglob("*"):
        if p.is_file() and set(p.parts) & nodes:
            if (p.name in {"command.txt", "report.rst"} or p.suffix == ".mat" or
                    p.name.endswith((".nii", ".nii.gz"))):
                to = dest / "node_evidence" / p.relative_to(cache)
                to.parent.mkdir(exist_ok=True, parents=True)
                shutil.copyfile(p, to)
    commands = list((dest / "node_evidence").rglob("command.txt"))
    ai_commands = [p.read_text() for p in commands if "init_aff" in p.parts and
                   "enhance_and_skullstrip_bold_wf" in p.parts]
    expected = "Rigid[0.1]" if mode == "rigid" else "Affine[0.1]"
    if not ai_commands or any(expected not in text for text in ai_commands):
        raise ValueError("Full-run initialization commands do not verify the assigned condition")
    row = dict(mode=mode, technical_checks_passed=True, scientific_acceptance=False,
               volumes=nvol, confound_rows=len(data), canonical_coverage_pct=coverage,
               same_MNI_grid_as_production=bool(same_grid), products=checks,
               target_sha256=sha(target), initialization_verified=expected,
               coreg_sources=sources,
               caveat="Coverage is descriptive; inspect native masks, SDC and registration before acceptance.")
    write_json(root / ("full-" + mode + "-validation.json"), row)
    print(f"VALIDATED {mode}: {nvol} volumes; 4 echoes; confounds aligned; coverage={coverage:.3f}%", flush=True)
    return 0


def make_report(root):
    pieces = ["<!doctype html><meta charset='utf-8'><title>11935 initialization tests</title>",
              "<h1>11935 paired initialization and full-run tests</h1>",
              "<p>Isolated experiment. Technical completion is not scientific acceptance. Production unchanged.</p>"]
    for mode in ("affine", "rigid"):
        validation = root / ("full-" + mode + "-validation.json")
        if validation.is_file():
            row = json.loads(validation.read_text())
            pieces.append(f"<h2>Full {mode}: canonical coverage {row['canonical_coverage_pct']:.3f}%</h2>")
            for name in ("native_postSDC.png", "MNI_mask.png"):
                pieces.append(f'<img style="max-width:100%" src="evidence/{mode}/{name}">')
    for seed in SEEDS:
        pieces.append(f"<h2>Paired seed {seed}: pre-SDC enhancement</h2>")
        for mode in ("affine", "rigid"):
            folder = root / "pairs" / f"seed_{seed}_{mode}"
            pieces.append("<h3>" + html.escape(mode) + "</h3>")
            for name in ("input_mask.png", "enhanced.png", "prior.png", "bias.png"):
                if (folder / name).is_file():
                    pieces.append(f'<img style="max-width:100%" src="{folder.relative_to(root)}/{name}">')
    (root / "index.html").write_text("\n".join(pieces))
    paths = [p for p in root.rglob("*") if p.is_file() and
             p.relative_to(root).parts[0] in {"inputs", "patch", "evidence", "pairs"}]
    write_json(root / "evidence-hashes.json", [dict(path=str(p.relative_to(root)), sha256=sha(p)) for p in sorted(paths)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-linux2"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--image", type=Path, default=Path("/ZPOOL/data/tools/fmriprep-25.2.5.simg"))
    parser.add_argument("--templateflow", type=Path, default=Path("/ZPOOL/data/tools/templateflow"))
    parser.add_argument("--licenses", type=Path, default=Path("/ZPOOL/data/tools/licenses"))
    parser.add_argument("--nprocs", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--inside", choices=("pairs", "validate"), help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=("affine", "rigid"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside:
        if Path.cwd() != Path("/out"):
            raise ValueError("Container stage must run in /out")
        return paired_tests() if args.inside == "pairs" else validate_full(args.mode)
    if args.output is None:
        parser.error("--output required")
    return host(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
