#!/usr/bin/env python3
"""Read-only paired coverage inspection. No eligibility decisions or image repair."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import hashlib
import html
import json
from pathlib import Path
import sys

import nibabel as nib
from nibabel.processing import resample_from_to
import numpy as np

import build_run_qc as qc

ROOT = Path(__file__).resolve().parents[1]
KEY = ("subject", "session", "task", "run")
PARAMETERS = ("RepetitionTime", "EchoTime", "FlipAngle", "PhaseEncodingDirection",
              "EffectiveEchoSpacing", "TotalReadoutTime", "SliceThickness",
              "SpacingBetweenSlices", "MultibandAccelerationFactor", "ParallelReductionFactorInPlane")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signature(path):
    info = path.stat()
    out = dict(path=str(path), size=info.st_size, mtime_ns=info.st_mtime_ns)
    if not path.name.endswith(".nii.gz"):
        out["sha256"] = sha(path)
    return out


def read_table(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def write_table(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def key(row):
    return tuple(row[k] for k in KEY)


def name(row):
    return "sub-{}_ses-{}_task-{}_run-{}".format(*key(row))


def boolean(value):
    if str(value).lower() not in {"true", "false"}:
        raise ValueError("Missing/invalid QC flag")
    return str(value).lower() == "true"


def select_pairs(project, tasks, sessions, controls, limit=None):
    rows = read_table(project / "qc/run_qc.tsv")
    eras = read_table(project / "qc/scanner_era/run_metrics.tsv")
    if len({key(r) for r in rows}) != len(rows) or len({key(r) for r in eras}) != len(eras):
        raise ValueError("Duplicate canonical QC or scanner-era keys")
    era = {key(r): r for r in eras}
    selected = []
    for row in rows:
        if row["task"] not in tasks or row["session"] not in sessions:
            continue
        if key(row) not in era:
            raise ValueError("Missing scanner-era linkage")
        # A stale era table must not silently be paired to a newer QC snapshot.
        for metric in ("brain_coverage_pct", "fd_mean", "tedana_rejected_components"):
            if not np.isclose(float(row[metric]), float(era[key(row)][metric]), atol=1e-8, rtol=0):
                raise ValueError("Scanner-era metrics differ from canonical QC; refresh linkage first")
        if era[key(row)]["software_era"] == "XA60":
            selected.append(dict(row, software_era="XA60"))
    cases = sorted([r for r in selected if boolean(r["brain_coverage_outlier"])],
                   key=lambda r: (float(r["brain_coverage_pct"]), key(r)))
    if limit:
        cases = cases[:limit]
    if not cases:
        raise ValueError("No flagged XA60 coverage cases in selected tasks/sessions")
    pairs, units = [], {}
    for case in cases:
        units[name(case)] = case
        pool = [r for r in selected if r["subject"] != case["subject"] and
                (r["task"], r["session"], r["run"]) == (case["task"], case["session"], case["run"]) and
                not boolean(r["brain_coverage_outlier"]) and boolean(r["qc_complete"]) and
                np.isfinite(float(r["fd_mean"]))]
        pool.sort(key=lambda r: (abs(float(r["fd_mean"]) - float(case["fd_mean"])), key(r)))
        chosen, subjects = [], set()
        for row in pool:
            if row["subject"] not in subjects:
                chosen.append(row)
                subjects.add(row["subject"])
            if len(chosen) == controls:
                break
        for rank, control in enumerate(chosen, 1):
            units[name(control)] = control
            pairs.append(dict(case=name(case), control=name(control), task=case["task"], session=case["session"],
                              run=case["run"], rank=rank,
                              fd_difference=abs(float(control["fd_mean"]) - float(case["fd_mean"]))))
        if not chosen:
            pairs.append(dict(case=name(case), control="", task=case["task"], session=case["session"],
                              run=case["run"], rank="", fd_difference=""))
    return cases, pairs, units


def optional_one(paths):
    paths = sorted(set(paths))
    return (paths[0], "available") if len(paths) == 1 else (None, "missing" if not paths else "ambiguous")


def resolve(project, row):
    stem = name(row)
    func = project / f"derivatives/fmriprep/sub-{row['subject']}/ses-{row['session']}/func"
    mask = project / row["fmriprep_brain_mask"]
    raw = project / row["bids_bold"]
    paths = {"mask": mask, "raw": raw,
             "bold": func / f"{stem}_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"}
    for label in ("mask", "raw", "bold"):
        if not paths[label].is_file():
            raise ValueError("Missing/ambiguous required " + label)
    candidates = [p for p in func.glob(stem + "_*.nii.gz") if
                  not {"space", "echo"} & qc.parse_entities(p.name).keys()]
    states = {}
    for label, suffix in (("native_ref", "_boldref.nii.gz"), ("native_mask", "_desc-brain_mask.nii.gz")):
        paths[label], states[label] = optional_one(p for p in candidates if p.name.endswith(suffix))
    subject = project / f"derivatives/fmriprep/sub-{row['subject']}"
    anatomicals = []
    for folder in (subject / "anat", subject / f"ses-{row['session']}/anat"):
        anatomicals.extend(folder.glob(f"*_space-{qc.TARGET_SPACE}*_desc-preproc_T1w.nii.gz"))
    paths["mni_t1"], states["mni_t1"] = optional_one(anatomicals)
    sidecar = raw.with_name(raw.name.replace(".nii.gz", ".json"))
    paths["sidecar"] = sidecar if sidecar.is_file() else None
    states["sidecar"] = "available" if paths["sidecar"] else "missing"
    return paths, states


def sampled_mean(path):
    image = nib.load(path)
    if len(image.shape) != 4 or image.shape[3] < 1:
        raise ValueError("Expected 4D BOLD")
    # Three separated volumes avoid reading the full 4D series into memory.
    indices = sorted({min(image.shape[3]-1, int(image.shape[3]*f)) for f in (0.25, 0.5, 0.75)})
    mean = np.zeros(image.shape[:3], dtype=np.float32)
    for index in indices:
        values = np.asarray(image.dataobj[..., index], dtype=np.float32)
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite sampled BOLD")
        mean += values / len(indices)
    return nib.Nifti1Image(mean, image.affine), indices


def on_grid(image, reference, order):
    if len(image.shape) != 3:
        raise ValueError("Expected 3D reference/mask")
    out = resample_from_to(image, reference, order=order) if image.shape != reference.shape or not np.allclose(
        image.affine, reference.affine, atol=1e-5) else image
    data = np.asarray(out.dataobj, dtype=np.float32)
    if not np.isfinite(data).all():
        raise ValueError("Nonfinite reference/mask")
    return data


def spatial_metrics(target, mask, mean):
    t = np.asarray(target.dataobj) > 0
    m = on_grid(mask, target, 0) > 0
    signal = on_grid(mean, target, 1)
    support = nib.Nifti1Image(np.ones(mask.shape, dtype=np.uint8), mask.affine)
    in_fov = on_grid(support, target, 0) > 0
    missing = t & ~m
    kept = signal[t & m]
    median = float(np.median(kept)) if kept.size else 0
    metrics = dict(fixed_reference_coverage_pct=float(100*np.sum(t & m)/t.sum()),
                   mask_grid_contains_target_pct=float(100*np.sum(t & in_fov)/t.sum()),
                   missing_target_voxels=int(missing.sum()),
                   retained_median_intensity=median,
                   missing_median_relative_intensity=float(np.median(signal[missing])/median)
                   if missing.any() and median > 0 else None)
    for pct in (1, 5, 10):
        metrics[f"missing_voxels_above_{pct}pct_retained_median_pct"] = (
            float(100*np.mean(signal[missing] > median*pct/100)) if missing.any() and median > 0 else None)
    return metrics, m, missing, signal


def montage(image, path, title, target=None, mask=None, fixed_mni=False, focus_positions=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    image = nib.as_closest_canonical(image)
    data = np.asarray(image.dataobj)
    if fixed_mni and not np.allclose(image.affine[:3, :3], np.diag(np.diag(image.affine[:3, :3])), atol=1e-5):
        raise ValueError("Fixed MNI montage requires orthogonal target axes")
    t = on_grid(target, image, 0) > 0 if target is not None else None
    m = on_grid(mask, image, 0) > 0 if mask is not None else None
    finite = data[np.isfinite(data) & (data > 0)]
    vmax = float(np.percentile(finite, 99)) if finite.size else 1
    fig, axes = plt.subplots(3, 7, figsize=(17, 8.4))
    positions = focus_positions or ((-60, -40, -20, 0, 20, 40, 60), (-90, -65, -40, -15, 10, 35, 60),
                                   (-40, -20, 0, 20, 40, 60, 80))
    for axis in range(3):
        for col, ax in enumerate(axes[axis]):
            if fixed_mni:
                index = int(round((positions[axis][col] - image.affine[axis, 3]) / image.affine[axis, axis]))
            else:
                index = int(round((0.08 + col*0.14)*(image.shape[axis]-1)))
            ax.axis("off")
            if not 0 <= index < image.shape[axis]:
                ax.text(.5, .5, "Outside image grid", transform=ax.transAxes, ha="center", fontsize=8)
                continue
            view = lambda a: np.take(a, index, axis=axis).T
            remaining = [i for i in range(3) if i != axis]
            zooms = nib.affines.voxel_sizes(image.affine)
            aspect = zooms[remaining[1]] / zooms[remaining[0]]
            ax.imshow(view(data), origin="lower", cmap="gray", vmin=0, vmax=vmax, aspect=aspect)
            for overlay, color in ((t, "#f4cb43"), (m, "#00dbdb")):
                if overlay is not None and view(overlay).any() and not view(overlay).all():
                    ax.contour(view(overlay), levels=[0.5], colors=[color], linewidths=.55)
            if t is not None and m is not None:
                ax.imshow(np.ma.masked_where(~view(t & ~m), np.ones(view(t).shape)), origin="lower",
                          cmap=ListedColormap(["#ff3737"]), alpha=.6, vmin=0, vmax=1, aspect=aspect)
            coordinate = image.affine[axis, axis]*index + image.affine[axis, 3]
            label = f"{'xyz'[axis]}={coordinate:.0f} mm" if fixed_mni else f"{'ijk'[axis]} slice {index}"
            ax.set_title(label, fontsize=8)
    fig.suptitle(title, fontsize=13, y=.99)
    fig.text(.02, .018, "Yellow: reference target. Cyan: fMRIPrep mask. Red: target outside mask. "
             "RAS-oriented display; intensity scaled independently. Native slices may be oblique and are not MNI aligned.", fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, .96))
    fig.savefig(path, dpi=120)
    plt.close(fig)


def process_one(project, private, row):
    folder = private / "runs" / name(row)
    folder.mkdir(parents=True)
    try:
        paths, states = resolve(project, row)
        signatures = [signature(p) for p in paths.values() if p is not None]
        target = nib.as_closest_canonical(nib.load(project / "qc/reference" / qc.TARGET_MASK_NAME))
        mask = nib.load(paths["mask"])
        mean, indices = sampled_mean(paths["bold"])
        raw_mean, raw_indices = sampled_mean(paths["raw"])
        metrics, mask_target, missing, signal = spatial_metrics(target, mask, mean)
        measured = qc.compute_coverage(project / "qc/reference" / qc.TARGET_MASK_NAME, paths["mask"])
        delta = measured - float(row["brain_coverage_pct"])
        if abs(delta) > 0.01:
            raise ValueError("Live mask coverage differs from canonical QC by >0.01 percentage points")
        metrics.update(recorded_coverage_pct=float(row["brain_coverage_pct"]),
                       canonical_recomputed_coverage_pct=measured, coverage_delta_pp=delta)
        mni = nib.Nifti1Image(signal, target.affine)
        mask_on_target = nib.Nifti1Image(mask_target.astype(np.uint8), target.affine)
        for filename, image in (("mni_sampled_mean.nii.gz", mni), ("missing_target_mask.nii.gz", nib.Nifti1Image(
                missing.astype(np.uint8), target.affine)), ("raw_echo2_sampled_mean.nii.gz", raw_mean)):
            nib.save(image, folder / filename)
        montage(mni, folder / "mni_bold.png", name(row) + " | MNI sampled BOLD", target, mask_on_target, True)
        if missing.any():
            positions = []
            for axis in range(3):
                peak = int(np.argmax(missing.sum(axis=tuple(i for i in range(3) if i != axis))))
                positions.append([float(target.affine[axis, 3] + target.affine[axis, axis]*(peak+offset))
                                  for offset in (-6, -4, -2, 0, 2, 4, 6)])
            montage(mni, folder / "missing_focus.png", name(row) + " | Individual peak missing-target planes",
                    target, mask_on_target, True, positions)
        montage(raw_mean, folder / "raw_bold.png", name(row) + " | Original BIDS echo-2 sampled BOLD")
        if paths["native_ref"]:
            ref = nib.load(paths["native_ref"])
            native_mask = nib.load(paths["native_mask"]) if paths["native_mask"] else None
            montage(ref, folder / "native_ref.png", name(row) + " | Native fMRIPrep reference", mask=native_mask)
        if paths["mni_t1"]:
            anatomy = nib.Nifti1Image(on_grid(nib.load(paths["mni_t1"]), target, 1), target.affine)
            montage(anatomy, folder / "mni_t1.png", name(row) + " | Subject MNI T1w / functional mask",
                    target, mask_on_target, True)
        parameters = {}
        if paths["sidecar"]:
            sidecar = json.loads(paths["sidecar"].read_text())
            parameters = {k: sidecar[k] for k in PARAMETERS if k in sidecar}
        if signatures != [signature(p) for p in paths.values() if p is not None]:
            raise ValueError("Source image changed during inspection")
        result = dict(run_key=name(row), status="inspection_generated", optional_evidence=states,
                      metrics=metrics, source_signatures=signatures, sampled_mni_volumes=indices,
                      sampled_raw_volumes=raw_indices, raw_shape=list(nib.load(paths["raw"]).shape),
                      raw_zooms=[float(v) for v in nib.load(paths["raw"]).header.get_zooms()],
                      acquisition_parameters=parameters,
                      interpretation="Human review required; zero exported signal is not proof of absent acquisition")
        write_json(folder / "evidence.json", result)
        return result
    except Exception as exc:
        result = dict(run_key=name(row), status="inspection_failed", reason=str(exc))
        write_json(folder / "error.json", result)
        return result


def page(title, body):
    return '<!doctype html><meta charset="utf-8"><title>' + html.escape(title) + '</title>' + \
        '<style>body{font:15px system-ui;margin:24px;max-width:1800px}img{width:100%}' \
        '.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}' \
        'pre{white-space:pre-wrap}td,th{padding:5px;border:1px solid #aaa}table{border-collapse:collapse}' \
        '@media(max-width:900px){.pair{grid-template-columns:1fr}}</style><h1>' + html.escape(title) + '</h1>' + body


def reports(private, cases, pairs, units, results):
    lookup = {r["run_key"]: r for r in results}
    links = []
    for case in cases:
        case_key = name(case)
        controls = [p["control"] for p in pairs if p["case"] == case_key and p["control"]]
        cards = []
        for ident in [case_key, *controls]:
            row, result = units[ident], lookup[ident]
            text = f'<section><h2>{html.escape(ident)}</h2><p>Coverage {float(row["brain_coverage_pct"]):.3f}%; '
            text += f'FD {float(row["fd_mean"]):.3f}; TEDANA rejected {row["tedana_rejected_components"]}.</p>'
            text += '<pre>' + html.escape(json.dumps(result.get("optional_evidence", result), indent=2)) + '</pre>'
            for image in ("mni_bold.png", "mni_t1.png", "missing_focus.png", "raw_bold.png", "native_ref.png"):
                if (private / "runs" / ident / image).exists():
                    text += f'<h3>{image}</h3><a href="runs/{ident}/{image}"><img src="runs/{ident}/{image}"></a>'
            evidence = "evidence.json" if result["status"] == "inspection_generated" else "error.json"
            text += f'<a href="runs/{ident}/{evidence}">Measurements/provenance or error</a></section>'
            cards.append(text)
        filename = case_key + ".html"
        body = '<p>Flagged case first; controls pass coverage only, same XA60/task/session/run, nearest mean FD. '
        body += 'Other QC flags are retained in run_inventory.tsv; controls may recur across pairs. '
        body += 'No automatic exclusion. Overview MNI planes match; missing-focus planes are individual to each run. '
        body += 'Native views are not voxel-aligned between participants.</p>'
        body += '<div class="pair">' + ''.join(cards) + '</div>'
        (private / filename).write_text(page(case_key, body))
        links.append(f'<li><a href="{filename}">{case_key}</a>: {float(case["brain_coverage_pct"]):.3f}%</li>')
    body = '<p>Private research images. Do not commit this directory or images to Git. '
    body += 'Read-only inspection; flags, eligibility and source images are unchanged. '
    body += 'Preprocessed zeros can arise from masking. Inspect original BIDS BOLD, native references and MNI anatomy '
    body += 'before attributing loss to acquisition. Cases are ordered by lowest coverage first.</p><ol>'
    body += ''.join(links) + '</ol><p>See measurements.tsv, pairs.tsv, run_inventory.tsv and per-run evidence.json.</p>'
    (private / "index.html").write_text(page("XA60 coverage inspection", body))


def build(args):
    cases, pairs, units = select_pairs(args.project_root, args.tasks.split(","), args.sessions.split(","), args.controls, args.max_cases)
    print(f"Selected {len(cases)} flagged cases, {sum(bool(p['control']) for p in pairs)} pairings, {len(units)} unique image runs.")
    print("Controls: same XA60/task/session/run; coverage-pass, nearest mean FD; with replacement across cases.")
    if args.dry_run:
        print("DRY RUN: no images read or files written.")
        return
    if args.private_dir.exists():
        raise ValueError("Use a new private directory; no existing results are overwritten")
    target = args.project_root / "qc/reference" / qc.TARGET_MASK_NAME
    provenance = json.loads((args.project_root / "qc/provenance.json").read_text())
    if sha(target) != provenance["coverage"]["target_mask_sha256"]:
        raise ValueError("Canonical target mask does not match QC provenance")
    sources = [args.project_root / p for p in ("qc/run_qc.tsv", "qc/scanner_era/run_metrics.tsv", "qc/provenance.json")]
    sources += [target, Path(__file__), Path(qc.__file__)]
    signatures = [signature(p) for p in sources]
    args.private_dir.mkdir(parents=True, mode=0o700)
    write_table(args.private_dir / "pairs.tsv", pairs)
    write_table(args.private_dir / "run_inventory.tsv", list(units.values()))
    results = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(process_one, args.project_root, args.private_dir, r) for r in units.values()]
        for future in as_completed(futures):
            results.append(future.result())
            print(f"Inspected {len(results)}/{len(units)} image runs; failures={sum(r['status']=='inspection_failed' for r in results)}", flush=True)
    reports(args.private_dir, cases, pairs, units, results)
    measured = [dict(run_key=r["run_key"], status=r["status"], **r.get("metrics", {}), reason=r.get("reason", "")) for r in results]
    fields = list(dict.fromkeys(k for r in measured for k in r))
    write_table(args.private_dir / "measurements.tsv", [{k: r.get(k, "") for k in fields} for r in measured])
    failed = [r for r in results if r["status"] == "inspection_failed"]
    optional_counts = {field: dict(Counter(r.get("optional_evidence", {}).get(field, "run_failed") for r in results))
                       for field in ("native_ref", "native_mask", "mni_t1", "sidecar")}
    for field, counts in optional_counts.items():
        print(f"{field}: {counts}")
    manifest = dict(schema=1, no_eligibility_changes=True, cases=len(cases), image_runs=len(units),
                    failed_runs=len(failed), optional_evidence=optional_counts, sources=signatures,
                    image_sources=[s for r in results for s in r.get("source_signatures", [])],
                    outputs=[dict(path=str(p.relative_to(args.private_dir)), sha256=sha(p))
                             for p in sorted(args.private_dir.rglob("*")) if p.is_file()])
    write_json(args.private_dir / "manifest.json", manifest)
    check(args)


def check(args):
    manifest = json.loads((args.private_dir / "manifest.json").read_text())
    if manifest.get("no_eligibility_changes") is not True or manifest["failed_runs"]:
        raise ValueError("Inspection incomplete; inspect private measurements.tsv/error.json")
    for record in manifest["sources"] + manifest["image_sources"]:
        if signature(Path(record["path"])) != record:
            raise ValueError("Inspection inputs changed")
    for record in manifest["outputs"]:
        if sha(args.private_dir / record["path"]) != record["sha256"]:
            raise ValueError("Inspection output changed")
    print(f"CHECK PASSED: {manifest['cases']} case comparisons / {manifest['image_runs']} image inspections generated and verified.")
    print("This validates the inspection package, NOT acquisition quality or exclusions.")
    print(f"Private browser report: {args.private_dir / 'index.html'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--tasks", default="ugr,socialdoors,doors")
    parser.add_argument("--sessions", default="01")
    parser.add_argument("--controls", type=int, default=2)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.project_root, args.private_dir = args.project_root.resolve(), args.private_dir.resolve()
    if args.project_root / "work" not in args.private_dir.parents or min(args.controls, args.jobs) < 1:
        parser.error("Use private project work/ directory and positive controls/jobs")
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("max-cases must be positive")
    if set(args.tasks.split(",")) - {"ugr", "socialdoors", "doors"} or set(args.sessions.split(",")) - {"01", "02"}:
        parser.error("Supported tasks: ugr,socialdoors,doors; sessions: 01,02")
    (build if args.command == "build" else check)(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
