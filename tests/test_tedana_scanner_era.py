from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest


CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


scanner = load("audit_tedana_scanner_era", CODE / "audit_tedana_scanner_era.py")


def test_protocol_summary_separates_invariance_and_era_effects() -> None:
    records = []
    for era, tr, reconstruction in (
        ("E11", "1.615", "old"),
        ("XA30", "1.615", "old"),
        ("XA60", "1.615", "new"),
    ):
        records.extend(
            (
                {"task": "trust", "run": "1", "echo": "1", "parameter": "TR", "software_era": era, "value": tr},
                {"task": "trust", "run": "1", "echo": "1", "parameter": "Reconstruction", "software_era": era, "value": reconstruction},
            )
        )
    records.append(
        {"task": "trust", "run": "1", "echo": "1", "parameter": "TR", "software_era": "XA60", "value": "1.700"}
    )

    rows = {row["parameter"]: row for row in scanner.summarize_protocol(records)}

    assert rows["TR"]["status"] == "varies_within_era"
    assert rows["Reconstruction"]["status"] == "differs_systematically_by_era"


@pytest.mark.parametrize(
    ("values", "total", "top10", "effective"),
    [
        ([0.5, 0.3, 0.2], 1.0, 1.0, 2.800094),
        ([50.0, 30.0, 20.0], 1.0, 1.0, 2.800094),
        ([0.4, 0.2], 0.6, 0.6, 1.889882),
    ],
)
def test_pca_spectrum_preserves_selected_variance(
    tmp_path: Path, values: list[float], total: float, top10: float, effective: float
) -> None:
    path = tmp_path / "pca.tsv"
    pd.DataFrame({"normalized variance explained": values}).to_csv(path, sep="\t", index=False)

    count, selected, top, rank = scanner.pca_spectrum(path)

    assert count == len(values)
    assert selected == pytest.approx(total)
    assert top == pytest.approx(top10)
    assert rank == pytest.approx(effective, rel=1e-5)


def test_within_subject_pair_allows_metadata_only_rows() -> None:
    common = {
        "subject": "10001", "task": "trust", "run": "1", "audit_status": "complete",
        "pca_components": 10, "selected_fraction_possible": 0.1,
        "selected_pca_variance": 0.9, "mean_fd": 0.1,
        "brain_mask_voxels": "", "echo_mean_signal_slope": "",
        "echo_tsnr_slope": "", "echo_standardized_dvars_slope": "",
    }
    rows = [
        {**common, "session": "01", "software_era": "E11"},
        {**common, "session": "02", "software_era": "XA60", "pca_components": 20},
    ]

    pair = scanner.within_subject_pairs(rows)[0]

    assert pair["second_minus_first_pca_components"] == 10.0
    assert pair["second_minus_first_brain_mask_voxels"] == ""


def test_dicom_records_include_protocol_grouping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Element:
        VR = "DS"
        keyword = "EchoTime"
        value = "13.8"

        class Tag:
            group = 0x0018
            is_private = False

        tag = Tag()

    class Dataset:
        def iterall(self):
            return [Element()]

    class Pydicom:
        @staticmethod
        def dcmread(*_args, **_kwargs):
            return Dataset()

    path = tmp_path / "one.dcm"
    path.touch()
    monkeypatch.setitem(sys.modules, "pydicom", Pydicom())

    records = scanner.dicom_parameters(
        [{"task": "trust", "run": "1", "software_era": "E11", "representative_dicom": str(path)}]
    )

    assert records[0]["echo"] == "dicom"
    assert scanner.summarize_protocol(records)[0]["parameter"] == "EchoTime"


def test_dicom_records_exclude_sensitive_and_private_elements(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class Tag:
        def __init__(self, group: int, private: bool = False):
            self.group = group
            self.is_private = private

    class Element:
        def __init__(self, keyword: str, vr: str, value: str, tag: Tag):
            self.keyword = keyword
            self.VR = vr
            self.value = value
            self.tag = tag

    class Dataset:
        def iterall(self):
            return [
                Element("EchoTime", "DS", "13.8", Tag(0x0018)),
                Element("InstanceCreationDate", "DA", "20260101", Tag(0x0008)),
                Element("StudyComments", "LT", "sensitive", Tag(0x0032)),
                Element("SoftwareVersions", "LO", "private", Tag(0x0021, private=True)),
                Element("SOPInstanceUID", "UI", "1.2.3", Tag(0x0008)),
            ]

    class Pydicom:
        @staticmethod
        def dcmread(*_args, **_kwargs):
            return Dataset()

    path = tmp_path / "one.dcm"
    path.touch()
    monkeypatch.setitem(sys.modules, "pydicom", Pydicom())

    records = scanner.dicom_parameters(
        [{"task": "trust", "run": "1", "software_era": "E11", "representative_dicom": str(path)}]
    )

    assert [row["parameter"] for row in records] == ["EchoTime"]


def test_tracked_dicom_mapping_columns_redact_raw_paths() -> None:
    assert "representative_dicom" not in scanner.DICOM_COLUMNS
    assert "source_scan_directory" not in scanner.DICOM_COLUMNS
    assert "series_description" not in scanner.DICOM_COLUMNS
