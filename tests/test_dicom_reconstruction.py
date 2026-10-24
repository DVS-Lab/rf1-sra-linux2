import importlib.util
import json
from pathlib import Path
import subprocess
import warnings

import pydicom
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from nibabel.nicom import ascconv

SPEC = importlib.util.spec_from_file_location("recon", Path(__file__).resolve().parents[1] / "code/inspect_dicom_reconstruction.py")
recon = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recon)


def header(enhanced=False):
    ds = Dataset()
    ds.SeriesNumber = 13
    ds.SeriesDescription = "task"
    ds.SoftwareVersions = "syngo MR XA60"
    ds.StudyInstanceUID = "1.2.3"
    ds.SeriesInstanceUID = "1.2.3.4"
    ds.PatientName = "DO_NOT_PRINT"
    if enhanced:
        frame = Dataset()
        echo = Dataset()
        echo.EffectiveEchoTime = 13.8
        frame.MREchoSequence = Sequence([echo])
        kind = Dataset()
        kind.ComplexImageComponent = "MAGNITUDE"
        frame.MRImageFrameTypeSequence = Sequence([kind])
        ds.PerFrameFunctionalGroupsSequence = Sequence([frame])
    else:
        ds.ImageType = ["ORIGINAL", "PRIMARY", "M"]
        ds.EchoTime = 13.8
    return ds


def row():
    return dict(subject="12345", session="02", task="doors", run="1", era="XA60",
                payload=dict(SeriesNumber=13, SeriesDescription="task", EchoTime=.0138))


def test_array_declarations_preserved_without_breaking_protocol_parser():
    block = '\n'.join([
        '### ASCCONV BEGIN ###',
        'asGPAData.__attribute__.size = 1',
        'asGPAData[0].lValue = 7',
        'sWipMemBlock.alFree.__attribute__.size = 2',
        'sWipMemBlock.alFree[0] = 3',
        'sWipMemBlock.alFree[1] = 8',
        '### ASCCONV END ###',
    ])
    parsed, _, declarations = recon.parse_protocol(block, ascconv.parse_ascconv)
    assert parsed['asGPAData'][0]['lValue'] == 7
    assert parsed['sWipMemBlock']['alFree'] == [3, 8]
    assert declarations == ['asGPAData.__attribute__.size = 1',
                            'sWipMemBlock.alFree.__attribute__.size = 2']


@pytest.mark.parametrize("enhanced", [False, True])
def test_magnitude_echo_identity_and_uid(enhanced):
    ds, r = header(enhanced), row()
    assert recon.matching_header(ds, r)
    r["payload"]["EchoTime"] = .06702
    assert not recon.matching_header(ds, r)
    r["payload"]["EchoTime"] = .0138
    r["payload"]["SeriesInstanceUID"] = "1.2.9"
    assert not recon.matching_header(ds, r)


def test_reject_phase():
    ds = header()
    ds.ImageType = ["ORIGINAL", "PRIMARY", "P"]
    assert not recon.matching_header(ds, row())


def test_session_two_never_falls_back_to_session_one(tmp_path):
    path = tmp_path / "Smith-SRA-12345/scans/13-task/file.dcm"
    path.parent.mkdir(parents=True)
    path.touch()
    with pytest.raises(ValueError, match="unique source"):
        recon.source_header(tmp_path, row(), 32, lambda p: header())


def test_multiple_studies_are_not_resolved_by_series_number(tmp_path):
    for folder in ("Smith-SRA-12345-2", "Smith-SRA-12345-2-supplement"):
        path = tmp_path / folder / "scans/13-task/file.dcm"
        path.parent.mkdir(parents=True)
        path.touch()
    def reader(path):
        ds = header()
        if "supplement" in str(path):
            ds.SeriesInstanceUID = "1.2.3.5"
        return ds
    with pytest.raises(ValueError, match="unique source"):
        recon.source_header(tmp_path, row(), 32, reader)


def test_sampling_separates_sessions_and_eras(tmp_path):
    for session in ("01", "02"):
        for number, version in enumerate(("XA30", "XA30", "XA60", "XA60"), 10001):
            path = tmp_path / f"sub-{number}/ses-{session}/func/sub-{number}_ses-{session}_task-doors_run-1_echo-1_part-mag_bold.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(dict(SoftwareVersions=version)))
    selected, population = recon.select_samples(tmp_path, ["01", "02"], ["XA30", "XA60"], 1)
    assert len(selected) == len(population) == 4
    assert all(v == 2 for v in population.values())


def test_private_ascconv_and_nested_enhanced_fields():
    ds = header(True)
    text = "### ASCCONV BEGIN ###\nsKSpace.lBaseResolution = 80\nsKSpace.uc2DInterpolation = 0x1\n### ASCCONV END ###\n"
    ds.add_new((0x0029, 0x0010), "LO", "SIEMENS CSA HEADER")
    ds.add_new((0x0029, 0x1020), "OB", text.encode())
    fields, extra = recon.extract_fields(ds, lambda *a: None, ascconv.parse_ascconv)
    assert extra["ascconv_blocks"] == 1
    assert fields["ASCCONV.sKSpace.lBaseResolution"] == ["80"]
    assert fields["ASCCONV.sKSpace.uc2DInterpolation"] == ["1"]
    assert fields["DICOM.EffectiveEchoTime"] == ['"13.8"']
    assert "DO_NOT_PRINT" not in json.dumps(fields)


def test_csa_decoding_and_failures_explicit():
    text = "### ASCCONV BEGIN ###\nsKSpace.lBaseResolution = 80\n### ASCCONV END ###\n"
    def csa(ds, kind):
        if kind == "image":
            raise ValueError("private detail must not be printed")
        return {"tags": {"MrPhoenixProtocol": {"items": [text]}, "FilterWidth": {"items": [2.0]}}}
    fields, extra = recon.extract_fields(header(), csa, ascconv.parse_ascconv)
    assert fields["CSA.FilterWidth"] == ["2.0"]
    assert extra["ascconv_blocks"] == 1
    assert extra["decoder_notes"][0]["status"] == "csa_decode_error"


def test_missing_protocol_never_counts_as_equal():
    rows = [dict(status="collected", task="doors", session="01", run="1", era=e, fields=f)
            for e, f in (("XA30", {"filter": ["0"]}), ("XA60", {}))]
    comparison = recon.compare(rows, ["XA30", "XA60"])
    assert comparison[0]["status"] == "incomplete_evidence"
    assert comparison[0]["XA60_coverage"] == "0/1"


def test_real_siemens_csa_phoenix_fixture():
    import gzip
    import nibabel
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from nibabel.nicom import csareader
    fixture = Path(nibabel.__file__).parent / "nicom/tests/data/siemens_dwi_0.dcm.gz"
    if not fixture.exists():
        pytest.skip("NiBabel Siemens fixture not distributed with this installation")
    with gzip.open(fixture, "rb") as stream:
        ds = pydicom.dcmread(stream, stop_before_pixels=True)
    fields, extra = recon.extract_fields(ds, csareader.get_csa_header, ascconv.parse_ascconv)
    assert extra["ascconv_blocks"] > 0
    assert "ASCCONV.sKSpace.lBaseResolution" in fields
    assert not any("error" in n["status"] for n in extra["decoder_notes"])


def test_end_to_end_header_only_ignored_outputs_and_umask(tmp_path):
    project, source = tmp_path / "project", tmp_path / "source"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / ".gitignore").write_text("/work/\n")
    original = {}
    for subject, version in (("12345", "XA30"), ("12346", "XA60")):
        sidecar = project / f"bids/sub-{subject}/ses-02/func/sub-{subject}_ses-02_task-doors_run-1_echo-1_part-mag_bold.json"
        sidecar.parent.mkdir(parents=True)
        sidecar.write_text(json.dumps(dict(SeriesNumber=13, SeriesDescription="task", EchoTime=.0138, SoftwareVersions=version)))
        path = source / f"Smith-SRA-{subject}-2/scans/13-task/file.dcm"
        path.parent.mkdir(parents=True)
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
        ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
        ds.update(header())
        ds.SoftwareVersions = version
        ds.PixelData = b"PIXELS_NOT_READ_OR_COPIED"
        ds.save_as(path)
        original[path] = path.read_bytes()
    out = project / "work/review"
    command = [__import__("sys").executable, str(Path(recon.__file__)), "--project", str(project),
               "--source-root", str(source), "--private-dir", str(out), "--eras", "XA30", "XA60"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DO_NOT_PRINT" not in result.stdout + result.stderr
    assert "1.2.3.4" not in result.stdout + result.stderr
    import gzip
    for path in out.glob("sample-*/header-private.json.gz"):
        with gzip.open(path, "rt") as stream:
            saved = json.load(stream)
        assert "7FE00010" not in saved
        assert "00100010" in saved  # Full header stays private, not a false anonymization claim.
    assert (out / "summary.md").stat().st_mode & 0o777 == 0o666
    assert out.stat().st_mode & 0o777 == 0o777
    assert all(path.read_bytes() == content for path, content in original.items())
    provenance = json.loads((out / "provenance.json").read_text())
    assert all(recon.sha(out / key) == value for key, value in provenance["outputs"].items())
    rerun = subprocess.run(command, capture_output=True, text=True)
    assert rerun.returncode == 2  # Never overwrite an existing evidence package.
