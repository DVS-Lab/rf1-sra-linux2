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
