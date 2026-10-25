#!/usr/bin/env python3
"""Read-only sampled DICOM/BIDS pixel parity; independent decoding, no resampling."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback
import warnings

import nibabel as nib
import numpy as np
import pydicom

import inspect_dicom_reconstruction as headers


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def signature(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def voxel_reindex(data, source_affine, target_affine, target_shape):
    """Map target indices to source indices using only a full-grid permutation/flip."""
    transform = np.linalg.solve(source_affine, target_affine)
    integer = np.rint(transform)
    require(np.allclose(transform, integer, rtol=0, atol=1e-3),
            'Grids not related by integer voxel reindexing; inspect geometry, not proof of interpolation')
    rotation = integer[:3, :3].astype(int)
    require(np.array_equal(integer[3], [0, 0, 0, 1])
            and np.all(np.sum(np.abs(rotation), axis=0) == 1)
            and np.all(np.sum(np.abs(rotation), axis=1) == 1),
            'Grid mapping is not a signed axis permutation')
    axes = np.argmax(np.abs(rotation), axis=0)
    result = data.transpose(tuple(axes))
    require(tuple(result.shape) == tuple(target_shape), 'Spatial shapes differ; no cropping or padding allowed')
    for target_axis, source_axis in enumerate(axes):
        sign = rotation[source_axis, target_axis]
        expected_offset = data.shape[source_axis] - 1 if sign == -1 else 0
        require(integer[source_axis, 3] == expected_offset, 'Grid does not cover the same full voxel extent')
        if sign == -1:
            result = np.flip(result, axis=target_axis)
    return result, transform.tolist()


def compare_volume(data, affine, image, tolerance):
    require(data.ndim == 3 and np.isfinite(data).all() and np.ptp(data) > 0,
            'Need one finite, nonconstant DICOM volume')
    require(len(image.shape) in (3, 4), 'Expected 3D or 4D single-echo NIfTI')
    expected, transform = voxel_reindex(data, affine, image.affine, image.shape[:3])
    # Decompress once, not separately for every candidate volume in a .nii.gz.
    actual = np.asanyarray(image.dataobj)
    if actual.ndim == 3:
        actual = actual[..., None]
    matches, best = [], None
    for time in range(actual.shape[3]):
        volume = actual[..., time]
        if not np.isfinite(volume).all():
            continue
        difference = np.asarray(volume, dtype=np.float64) - expected
        error = float(np.max(np.abs(difference)))
        if best is None or error < best['max_absolute_error']:
            best = dict(volume_index=time, max_absolute_error=error,
                        rmse=float(np.sqrt(np.mean(difference * difference))))
        if error <= tolerance:
            matches.append(dict(volume_index=time, max_absolute_error=error,
                                exact_equal=bool(np.array_equal(volume, expected))))
    return dict(status='PASS' if len(matches) == 1 else 'REVIEW', matches=matches,
                nearest=best, voxel_transform=transform, spatial_voxels=int(data.size),
                candidate_volumes=int(actual.shape[3]), absolute_tolerance=tolerance)


def decode(ds):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        from nibabel.nicom.dicomwrappers import wrapper_from_data
        wrapper = wrapper_from_data(ds)
        require(wrapper.is_mosaic or wrapper.is_multiframe, 'Unsupported single-file volume layout')
        data = np.asarray(wrapper.get_data(), dtype=np.float64)
        while data.ndim > 3 and data.shape[-1] == 1:
            data = data[..., 0]
        # NiBabel DICOM wrappers use patient LPS; NIfTI uses RAS world coordinates.
        affine = np.diag([-1., -1., 1., 1.]) @ wrapper.affine
    return data, affine, np.asarray(wrapper.scale_factors).tolist()


def reconvert(source, destination, image):
    input_dir, output_dir = destination / 'input', destination / 'converted'
    input_dir.mkdir()
    output_dir.mkdir()
    # Independent copy: no links and no possibility of converter writes to source.
    shutil.copyfile(source, input_dir / 'volume.dcm')
    command = ['apptainer', 'exec', '--cleanenv', '--containall',
               '--bind', f'{destination}:/audit:rw', str(image), 'dcm2niix',
               '-b', 'y', '-ba', 'n', '-z', 'n', '-x', 'i', '-f', 'converted',
               '-o', '/audit/converted', '/audit/input']
    with (destination / 'converter-private.log').open('w') as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)
    outputs = sorted(output_dir.glob('*.nii'))
    require(len(outputs) == 1, 'Isolated conversion did not produce exactly one NIfTI')
    return outputs[0], command


def inspect(row, destination, args):
    source, sidecar = Path(row['source']), Path(row['bids'])
    require(source.resolve().is_relative_to(args.source_root.resolve()), 'Source outside approved source root')
    require(sidecar.resolve().is_relative_to((args.project / 'bids').resolve()), 'Sidecar outside canonical BIDS')
    require(digest(sidecar) == row['bids_sha256'], 'BIDS metadata changed since header inventory')
    require(signature(source) == (row['source_size'], row['source_mtime_ns']), 'DICOM changed since inventory')
    bids = sidecar.with_suffix('.nii.gz')
    if not bids.exists():
        bids = sidecar.with_suffix('.nii')
    before = {str(p): signature(p) for p in (source, sidecar, bids)}
    ds = pydicom.dcmread(source)
    payload = json.loads(sidecar.read_text())
    require(headers.matching_header(ds, dict(row, payload=payload)), 'Live DICOM metadata no longer matches candidate')
    require(str(ds.SeriesInstanceUID) and str(ds.SOPInstanceUID), 'Source UID missing')
    data, affine, scales = decode(ds)
    image = nib.load(bids)
    canonical = compare_volume(data, affine, image, args.absolute_tolerance)
    result = dict(era=row['era'], session=row['session'], task=row['task'], run=row['run'],
                  subject=row['subject'], source=str(source), bids=str(bids),
                  series_uid=str(ds.SeriesInstanceUID), sop_uid=str(ds.SOPInstanceUID),
                  dicom_scaling=scales, source_sha256=digest(source), bids_sha256=digest(bids),
                  original_link=row['mapping']['link'], canonical=canonical)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        from nibabel.nicom import ascconv, csareader
        fields, _ = headers.extract_fields(ds, csareader.get_csa_header, ascconv.parse_ascconv)
    result['reconstruction_fields'] = {k: v for k, v in fields.items()
                                       if 'DistortionCorr' in k or k == 'DICOM.VolumetricProperties'
                                       or k.startswith('ASCCONV.alTE[')}
    converted, command = reconvert(source, destination, args.converter_image)
    result['isolated_conversion'] = compare_volume(data, affine, nib.load(converted), args.absolute_tolerance)
    result['converter_command'] = command
    result['converter_metadata'] = json.loads(converted.with_suffix('.json').read_text())
    result['original_converter_version'] = payload.get('ConversionSoftwareVersion', 'unknown')
    require(before == {str(p): signature(p) for p in (source, sidecar, bids)}, 'Input changed during pixel verification')
    result['status'] = ('PASS' if canonical['status'] == result['isolated_conversion']['status'] == 'PASS'
                        else 'REVIEW')
    return result


def run(args):
    args.project = args.project.resolve()
    output = args.output.resolve()
    require(output.is_relative_to(args.project / 'work') and output != args.project / 'work'
            and not output.exists(), 'Use a new output directory inside project work/')
    require(subprocess.run(['git', '-C', str(args.project), 'check-ignore', '-q', str(output / 'report.json')]).returncode == 0,
            'Output must be Git ignored')
    require(args.converter_image.is_file(), 'Converter container is unavailable')
    rows = json.loads(args.inventory.read_text())['samples']
    rows = [r for r in rows if r.get('status') == 'collected' and r['session'] in args.sessions]
    require(rows, 'No collected samples for requested sessions')
    os.umask(0o000)
    output.mkdir(parents=True)
    print(f'Preparing read-only pixel check for {len(rows)} samples; hashing converter container', flush=True)
    provenance = dict(inventory_sha256=digest(args.inventory), script_sha256=digest(Path(__file__)),
                      header_helper_sha256=digest(Path(headers.__file__)),
                      converter_image=str(args.converter_image), converter_image_sha256=digest(args.converter_image),
                      nibabel=nib.__version__, pydicom=pydicom.__version__, numpy=np.__version__)
    results = []
    for number, row in enumerate(rows, 1):
        folder = output / f'sample-{number:03d}'
        folder.mkdir()
        print(f"START {number}/{len(rows)} {row['era']} ses-{row['session']} {row['task']}", flush=True)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                result = inspect(row, folder, args)
        except Exception as exc:
            (folder / 'error-private.txt').write_text(traceback.format_exc())
            result = {k: row[k] for k in ('era', 'session', 'task', 'run', 'subject')}
            result.update(status='ERROR', error_type=type(exc).__name__)
        headers.dump(folder / 'result-private.json', result)
        results.append(result)
        print(f"Sample {number}/{len(rows)} {row['era']} ses-{row['session']} {row['task']}: {result['status']}", flush=True)
    headers.dump(output / 'report-private.json', dict(provenance=provenance, samples=results))
    counts = Counter((r['era'], r['session'], r['status']) for r in results)
    lines = ['# DICOM/raw-BIDS sampled pixel parity', '',
             'One saved echo-1 DICOM volume per sampled run, all spatial voxels; not every echo/timepoint.',
             'Only axis permutations/flips and header-defined intensity scaling are allowed. No resampling.',
             'PASS requires a unique voxelwise match in canonical BIDS and isolated conversion.',
             'REVIEW/ERROR is inconclusive, not proof of interpolation or failed acquisition.',
             'No production inputs, processing, QC rules or exclusions changed.', '']
    lines += [f'{era} ses-{session}: {status}={count}' for (era, session, status), count in sorted(counts.items())]
    passed = all(r['status'] == 'PASS' for r in results)
    lines += ['', 'CHECK PASSED: sampled pixel parity.' if passed else 'REVIEW REQUIRED: inspect private per-sample results.']
    summary = '\n'.join(lines) + '\n'
    (output / 'summary.md').write_text(summary)
    print(summary)
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, default=Path('/ZPOOL/data/sourcedata/sourcedata/rf1-sra'))
    parser.add_argument('--converter-image', type=Path, default=Path('/ZPOOL/data/tools/heudiconv-1.4.0.sif'))
    parser.add_argument('--sessions', nargs='+', choices=('01', '02'), default=['01', '02'])
    parser.add_argument('--absolute-tolerance', type=float, default=1e-4)
    args = parser.parse_args()
    require(np.isfinite(args.absolute_tolerance) and 0 <= args.absolute_tolerance <= 1e-3, 'Tolerance must be between 0 and 0.001')
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
