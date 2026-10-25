import itertools
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import nibabel as nib
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
import check_dicom_bids_pixels as pixels


@pytest.mark.parametrize('axes', list(itertools.permutations(range(3))))
@pytest.mark.parametrize('signs', list(itertools.product((-1, 1), repeat=3)))
def test_all_axis_permutations_and_flips(axes, signs):
    data = np.arange(3 * 4 * 5).reshape(3, 4, 5)
    source_affine = np.array([[2.7, 0, 0, -50], [0, 2.7, 0, 30], [0, 0, 2.97, -20], [0, 0, 0, 1]])
    transform = np.zeros((4, 4))
    transform[3, 3] = 1
    expected = data.transpose(axes)
    for target, source in enumerate(axes):
        transform[source, target] = signs[target]
        if signs[target] < 0:
            transform[source, 3] = data.shape[source] - 1
            expected = np.flip(expected, axis=target)
    actual, _ = pixels.voxel_reindex(data, source_affine, source_affine @ transform, expected.shape)
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize('kind', ['fractional', 'scale', 'crop', 'offset'])
def test_no_resampling_cropping_or_geometry_fitting(kind):
    data, affine, shape = np.arange(60).reshape(3, 4, 5), np.eye(4), (3, 4, 5)
    if kind == 'fractional':
        affine[0, 3] = .2
    elif kind == 'scale':
        affine[0, 0] = 2
    elif kind == 'offset':
        affine[0, 3] = 1
    else:
        shape = (2, 4, 5)
    with pytest.raises(ValueError):
        pixels.voxel_reindex(data, np.eye(4), affine, shape)


def test_unique_timepoint_match_without_time_assumption():
    data = np.arange(60, dtype=np.float64).reshape(3, 4, 5)
    image = nib.Nifti1Image(np.stack([data + 1, data, data + 3], axis=-1), np.eye(4))
    result = pixels.compare_volume(data, np.eye(4), image, 1e-4)
    assert result['status'] == 'PASS'
    assert result['matches'] == [dict(volume_index=1, max_absolute_error=0., exact_equal=True)]


@pytest.mark.parametrize('kind', ['blur', 'gain', 'ambiguous', 'nan'])
def test_mismatch_is_review_not_interpolation_claim(kind):
    data = np.arange(60, dtype=float).reshape(3, 4, 5)
    actual = data.copy()
    if kind == 'blur':
        actual[1] = (data[0] + 2 * data[1] + data[2]) / 4
        actual[0] = (data[0] + data[1]) / 2
    elif kind == 'gain':
        actual = data * 2
    elif kind == 'nan':
        actual[0, 0, 0] = np.nan
    else:
        actual = np.stack([data, data], axis=-1)
    result = pixels.compare_volume(data, np.eye(4), nib.Nifti1Image(actual, np.eye(4)), 1e-4)
    assert result['status'] == 'REVIEW'


def test_nifti_header_scaling_used(tmp_path):
    raw = np.arange(60, dtype=np.int16).reshape(3, 4, 5)
    image = nib.Nifti1Image(raw, np.eye(4))
    image.header.set_slope_inter(2, 10)
    path = tmp_path / 'scaled.nii.gz'
    nib.save(image, path)
    result = pixels.compare_volume(raw * 2. + 10, np.eye(4), nib.load(path), 1e-4)
    assert result['status'] == 'PASS' and result['matches'][0]['exact_equal']


def test_dicom_lps_to_ras_and_scaling(monkeypatch):
    from nibabel.nicom import dicomwrappers
    data = np.arange(60, dtype=float).reshape(3, 4, 5)
    wrapper = SimpleNamespace(is_mosaic=True, is_multiframe=False, get_data=lambda: data,
                              affine=np.eye(4), scale_factors=np.array([[2, 10]]))
    monkeypatch.setattr(dicomwrappers, 'wrapper_from_data', lambda ds: wrapper)
    actual, affine, scaling = pixels.decode(object())
    np.testing.assert_array_equal(actual, data)
    np.testing.assert_array_equal(affine, np.diag([-1, -1, 1, 1]))
    assert scaling == [[2, 10]]


def test_converter_cannot_write_source_and_command_disables_3d_rotation(tmp_path, monkeypatch):
    source = tmp_path / 'source.dcm'
    source.write_bytes(b'original')
    destination = tmp_path / 'isolated'
    destination.mkdir()
    def convert(command, **kwargs):
        assert command[:4] == ['apptainer', 'exec', '--cleanenv', '--containall']
        assert str(source) not in ' '.join(command)
        assert command[command.index('-x') + 1] == 'i'
        assert command[-1] == '/audit/input'
        assert (destination / 'input/volume.dcm').read_bytes() == b'original'
        (destination / 'input/volume.dcm').write_bytes(b'converter write')
        (destination / 'converted/output.nii').write_bytes(b'output')
    monkeypatch.setattr(pixels.subprocess, 'run', convert)
    path, _ = pixels.reconvert(source, destination, Path('/tools/test.sif'))
    assert source.read_bytes() == b'original' and path.is_file()


def test_no_constant_source_or_5d_output():
    with pytest.raises(ValueError, match='nonconstant'):
        pixels.compare_volume(np.zeros((3, 4, 5)), np.eye(4), None, 0)
    with pytest.raises(ValueError, match='3D or 4D'):
        pixels.compare_volume(np.arange(60).reshape(3, 4, 5), np.eye(4),
                              nib.Nifti1Image(np.zeros((3, 4, 5, 2, 2)), np.eye(4)), 0)


def test_full_stack_affine_removes_adjacent_rounding_not_pixel_differences():
    positions = np.zeros((51, 3))
    positions[:, 2] = np.arange(51) * 2.97
    positions[1, 2] += .00044
    affine = np.diag([2.7, 2.7, 2.97044, 1])
    wrapper = SimpleNamespace(is_multiframe=True, affine=affine, slice_normal=np.array([0, 0, 1]),
        frames=[SimpleNamespace(PlanePositionSequence=[SimpleNamespace(ImagePositionPatient=p)]) for p in positions])
    corrected = pixels.volume_affine(wrapper, (3, 4, 51))
    assert corrected[2, 2] == pytest.approx(2.97)
    np.testing.assert_array_equal(wrapper.affine, affine)
    data = np.arange(3 * 4 * 51, dtype=float).reshape(3, 4, 51)
    image = nib.Nifti1Image(data, np.diag([2.7, 2.7, 2.97, 1]))
    assert pixels.compare_volume(data, corrected, image, 1e-4)['status'] == 'PASS'
    changed = data.copy()
    changed[0, 0, 0] += 1
    assert pixels.compare_volume(changed, corrected, image, 1e-4)['status'] == 'REVIEW'
    positions[1, 2] += .1
    with pytest.raises(ValueError, match='Nonuniform'):
        pixels.volume_affine(wrapper, (3, 4, 51))


def test_retry_keeps_order_and_requires_identical_inventory_and_converter():
    row = dict(era='XA60', subject='12345', session='01', task='doors', run='1')
    provenance = dict(inventory_sha256='abc', converter_image_sha256='def')
    previous = dict(provenance=provenance, samples=[dict(row, status='PASS')])
    assert pixels.retry_rows([row], previous, provenance) == previous['samples']
    for changed in [dict(provenance, inventory_sha256='other'), dict(provenance, converter_image_sha256='other')]:
        with pytest.raises(ValueError):
            pixels.retry_rows([row], previous, changed)
    with pytest.raises(ValueError, match='order'):
        pixels.retry_rows([dict(row, task='socialdoors')], previous, provenance)


@pytest.mark.parametrize('change_passed_input', [False, True])
def test_retry_run_never_reconverts_pass_and_rejects_changed_input(tmp_path, monkeypatch, change_passed_input):
    root = tmp_path / 'project'
    root.mkdir()
    sidecar = root / 'sample.json'
    sidecar.write_text('{}')
    bids = sidecar.with_suffix('.nii.gz')
    bids.write_bytes(b'original NIfTI')
    source = root / 'source.dcm'
    source.write_bytes(b'original DICOM')
    container = root / 'container.sif'
    container.write_bytes(b'converter')
    row = dict(era='XA30', session='01', subject='12345', task='doors', run='1',
               source=str(source), bids=str(sidecar), bids_sha256=pixels.digest(sidecar), status='collected')
    second = dict(row, subject='12346')
    inventory = root / 'inventory.json'
    inventory.write_text(json.dumps(dict(samples=[row, second])))
    result = dict(row, bids=str(bids), status='PASS', source_sha256=pixels.digest(source), bids_sha256=pixels.digest(bids),
                  canonical=dict(status='PASS', absolute_tolerance=1e-4),
                  isolated_conversion=dict(status='PASS', absolute_tolerance=1e-4))
    previous = root / 'old.json'
    previous.write_text(json.dumps(dict(provenance=dict(inventory_sha256=pixels.digest(inventory),
        converter_image_sha256=pixels.digest(container)), samples=[result, dict(second, status='ERROR')])))
    original = previous.read_bytes()
    args = SimpleNamespace(project=root, output=root / 'work/retry', inventory=inventory,
        converter_image=container, retry_report=previous, sessions=['01'], absolute_tolerance=1e-4)
    monkeypatch.setattr(pixels.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=0))
    calls = []
    def inspect(row, folder, args):
        calls.append(row['subject'])
        assert folder.name == 'sample-002'
        return dict(row, status='PASS')
    monkeypatch.setattr(pixels, 'inspect', inspect)
    if change_passed_input:
        bids.write_bytes(b'changed')
        with pytest.raises(ValueError, match='inputs changed'):
            pixels.run(args)
        assert not calls
    else:
        assert pixels.run(args) == 0
        assert calls == ['12346']
        report = json.loads((args.output / 'report-private.json').read_text())
        assert report['samples'][0] == result
    assert previous.read_bytes() == original
