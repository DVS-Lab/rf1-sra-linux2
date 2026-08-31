from __future__ import annotations

import sys
import types
from collections import namedtuple

import pytest

sys.path.insert(0, __file__.rsplit("/tests/", 1)[0] + "/code")

from heudiconv_grouping import group_multi_source_session  # noqa: E402


SeqInfo = namedtuple("SeqInfo", "series_id label")


def dicom_path(source: int, scan: int, name: str = "T1w") -> str:
    return (
        "/out/source/Smith-SRA-11116-2/scans/"
        f"{source:02d}{scan:04d}-{name}/resources/DICOM/files/example.dcm"
    )


def test_custom_grouping_makes_repeated_visit_series_ids_unique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], str, bool]] = []

    def fake_group(files, grouping, dcmfilter=None, flatten=False):
        calls.append((files, grouping, flatten))
        return {SeqInfo("1-T1w", files[0]): files}

    package = types.ModuleType("heudiconv")
    dicoms = types.ModuleType("heudiconv.dicoms")
    dicoms.group_dicoms_into_seqinfos = fake_group
    monkeypatch.setitem(sys.modules, "heudiconv", package)
    monkeypatch.setitem(sys.modules, "heudiconv.dicoms", dicoms)

    first = dicom_path(1, 1)
    second = dicom_path(2, 1)
    grouped = group_multi_source_session([second, first], None, SeqInfo)

    assert [seqinfo.series_id for seqinfo in grouped] == [
        "1000001-T1w",
        "2000001-T1w",
    ]
    assert list(grouped.values()) == [[first], [second]]
    assert calls == [([first], "studyUID", True), ([second], "studyUID", True)]


def test_custom_grouping_rejects_unprefixed_scan_paths() -> None:
    path = (
        "/out/source/Smith-SRA-11116-2/scans/1-T1w/"
        "resources/DICOM/files/example.dcm"
    )
    with pytest.raises(RuntimeError, match="source-prefixed scan alias"):
        group_multi_source_session([path], None, SeqInfo)
