from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from source_layout import (  # noqa: E402
    load_supplemental_sources,
    prepare_merged_source,
    required_runs_for,
    supplemental_sources_for,
)


def write_manifest(path: Path, source_relative: str, status: str = "active") -> None:
    path.write_text(
        "subject\tsession\tstatus\tsource_relative\trequired_runs\treason\n"
        f"11116\t02\t{status}\t{source_relative}\t"
        "doors:1,socialdoors:1\tcompletes same session\n"
    )


def make_scan(source: Path, name: str) -> Path:
    dicoms = source / "scans" / name / "resources" / "DICOM" / "files"
    dicoms.mkdir(parents=True)
    (dicoms / "example.dcm").write_text("dcm")
    return source / "scans" / name


def test_manifest_is_session_specific(tmp_path: Path) -> None:
    manifest = tmp_path / "sources.tsv"
    write_manifest(
        manifest,
        "Smith-SRA-11116-2-socialdoors/Smith-SRA-11116-2-socialdoors",
    )
    specs = load_supplemental_sources(manifest)
    assert len(supplemental_sources_for(specs, "sub-11116", "ses-02")) == 1
    assert supplemental_sources_for(specs, "11116", "01") == []
    assert required_runs_for(specs, "11116", "02") == [
        ("doors", 1),
        ("socialdoors", 1),
    ]


@pytest.mark.parametrize("unsafe", ["/absolute/path", "../escape", "folder/../escape"])
def test_manifest_rejects_unsafe_paths(tmp_path: Path, unsafe: str) -> None:
    manifest = tmp_path / "sources.tsv"
    write_manifest(manifest, unsafe)
    with pytest.raises(ValueError, match="unsafe source_relative"):
        load_supplemental_sources(manifest)


def test_manifest_rejects_invalid_required_runs(tmp_path: Path) -> None:
    manifest = tmp_path / "sources.tsv"
    manifest.write_text(
        "subject\tsession\tstatus\tsource_relative\trequired_runs\treason\n"
        "11116\t02\tactive\treturn/return\tsocialdoors\tbad requirement\n"
    )
    with pytest.raises(ValueError, match="invalid required_runs"):
        load_supplemental_sources(manifest)


def test_paused_source_blocks_merged_session(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    primary = source_root / "Smith-SRA-11116-2" / "Smith-SRA-11116-2"
    supplement = (
        source_root
        / "Smith-SRA-11116-2-socialdoors"
        / "Smith-SRA-11116-2-socialdoors"
    )
    make_scan(primary, "1-T1w")
    make_scan(supplement, "2-SocialDoors_face")
    manifest = tmp_path / "sources.tsv"
    write_manifest(
        manifest,
        "Smith-SRA-11116-2-socialdoors/Smith-SRA-11116-2-socialdoors",
        status="paused",
    )

    with pytest.raises(ValueError, match="supplemental source is paused"):
        prepare_merged_source(source_root, manifest, "11116", "02", None)


def test_merged_view_preserves_both_visits_and_scan_labels(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    primary = source_root / "Smith-SRA-11116-2" / "Smith-SRA-11116-2"
    supplement = (
        source_root
        / "Smith-SRA-11116-2-socialdoors"
        / "Smith-SRA-11116-2-socialdoors"
    )
    make_scan(primary, "1-T1w-anat_mpg_07sag_iso")
    make_scan(primary, "2-localizer")
    make_scan(supplement, "1-T1w-anat_mpg_07sag_iso")
    make_scan(supplement, "2-SocialDoors_face")
    manifest = tmp_path / "sources.tsv"
    write_manifest(
        manifest,
        "Smith-SRA-11116-2-socialdoors/Smith-SRA-11116-2-socialdoors",
    )

    template, sources = prepare_merged_source(
        source_root, manifest, "11116", "02", tmp_path / "stage"
    )

    assert template == (
        "/out/source/Smith-SRA-{subject}-2/scans/*/*/DICOM/files/*.dcm"
    )
    assert sources == [primary, supplement]
    links = sorted((tmp_path / "stage/source/Smith-SRA-11116-2/scans").iterdir())
    assert [path.name for path in links] == [
        "010001-T1w-anat_mpg_07sag_iso",
        "010002-localizer",
        "020001-T1w-anat_mpg_07sag_iso",
        "020002-SocialDoors_face",
    ]
    assert all(path.is_symlink() for path in links)
    assert os.readlink(links[2]).startswith("/sourcedata/Smith-SRA-11116-2-socialdoors/")


def test_merged_view_requires_dicoms_in_every_reviewed_source(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    primary = source_root / "Smith-SRA-11116-2" / "Smith-SRA-11116-2"
    supplement = (
        source_root
        / "Smith-SRA-11116-2-socialdoors"
        / "Smith-SRA-11116-2-socialdoors"
    )
    make_scan(primary, "1-T1w")
    (supplement / "scans").mkdir(parents=True)
    manifest = tmp_path / "sources.tsv"
    write_manifest(
        manifest,
        "Smith-SRA-11116-2-socialdoors/Smith-SRA-11116-2-socialdoors",
    )

    with pytest.raises(ValueError, match="no DICOMs"):
        prepare_merged_source(source_root, manifest, "11116", "02", None)
