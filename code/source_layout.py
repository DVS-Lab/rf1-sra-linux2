#!/usr/bin/env python3
"""Validate and stage reviewed multi-folder DICOM session layouts."""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class SupplementalSource:
    subject: str
    session: str
    status: str
    source_relative: PurePosixPath
    reason: str


REQUIRED_COLUMNS = {"subject", "session", "status", "source_relative", "reason"}
VALID_STATUSES = {"active", "paused"}


def load_supplemental_sources(path: Path) -> list[SupplementalSource]:
    if not path.is_file():
        raise ValueError(f"supplemental source manifest not found: {path}")
    specs: list[SupplementalSource] = []
    seen: set[tuple[str, str, PurePosixPath]] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"supplemental source manifest has no header: {path}")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(
                "supplemental source manifest lacks column(s): "
                + ", ".join(sorted(missing))
            )
        for line_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue
            subject = (row.get("subject") or "").strip().removeprefix("sub-")
            session = (row.get("session") or "").strip().removeprefix("ses-").zfill(2)
            status = (row.get("status") or "").strip().lower()
            source_text = (row.get("source_relative") or "").strip()
            reason = (row.get("reason") or "").strip()
            if not re.fullmatch(r"\d+", subject):
                raise ValueError(f"invalid subject at {path}:{line_number}: {subject!r}")
            if session not in {"01", "02"}:
                raise ValueError(f"invalid session at {path}:{line_number}: {session!r}")
            if status not in VALID_STATUSES:
                raise ValueError(f"invalid status at {path}:{line_number}: {status!r}")
            source_relative = PurePosixPath(source_text)
            if (
                not source_text
                or source_relative.is_absolute()
                or any(part in {"", ".", ".."} for part in source_relative.parts)
            ):
                raise ValueError(
                    f"unsafe source_relative at {path}:{line_number}: {source_text!r}"
                )
            if not reason:
                raise ValueError(f"missing review reason at {path}:{line_number}")
            key = (subject, session, source_relative)
            if key in seen:
                raise ValueError(f"duplicate supplemental source at {path}:{line_number}")
            seen.add(key)
            specs.append(
                SupplementalSource(subject, session, status, source_relative, reason)
            )
    return specs


def supplemental_sources_for(
    specs: list[SupplementalSource], subject: str, session: str
) -> list[SupplementalSource]:
    subject = subject.removeprefix("sub-")
    session = session.removeprefix("ses-").zfill(2)
    return [spec for spec in specs if spec.subject == subject and spec.session == session]


def primary_source_dir(source_root: Path, subject: str, session: str) -> Path:
    subject = subject.removeprefix("sub-")
    session = session.removeprefix("ses-").zfill(2)
    if session == "01" and subject == "11891":
        return source_root / "11891" / "Smith-SRA-11891" / "Smith-SRA-11891"
    if session == "01" and subject == "12018":
        return source_root / "Smith-SRA-12018" / "Smith-SRA-"
    folder_subject = subject if session == "01" else f"{subject}-2"
    return source_root / f"Smith-SRA-{folder_subject}" / f"Smith-SRA-{folder_subject}"


def validate_source_dir(path: Path) -> list[Path]:
    scans = path / "scans"
    if not scans.is_dir():
        raise ValueError(f"source scan directory not found: {scans}")
    scan_dirs = sorted(item for item in scans.iterdir() if item.is_dir())
    if not any(any(scan.glob("*/DICOM/files/*.dcm")) for scan in scan_dirs):
        raise ValueError(f"no DICOMs found under source scan directory: {scans}")
    return scan_dirs


def _scan_label(name: str) -> str:
    return name.split("-", 1)[1] if "-" in name else name


def prepare_merged_source(
    source_root: Path,
    manifest: Path,
    subject: str,
    session: str,
    output_root: Path | None,
) -> tuple[str, list[Path]]:
    specs = supplemental_sources_for(
        load_supplemental_sources(manifest), subject, session
    )
    if not specs:
        raise ValueError(f"no reviewed supplemental sources for sub-{subject} ses-{session}")
    paused = [spec for spec in specs if spec.status == "paused"]
    if paused:
        reasons = "; ".join(spec.reason for spec in paused)
        raise ValueError(
            f"supplemental source is paused for sub-{subject} ses-{session}: {reasons}"
        )

    sources = [primary_source_dir(source_root, subject, session)]
    sources.extend(source_root.joinpath(*spec.source_relative.parts) for spec in specs)
    inventories = [(source, validate_source_dir(source)) for source in sources]

    folder_subject = subject if session == "01" else f"{subject}-2"
    template = (
        f"/out/source/Smith-SRA-{{subject}}{'-2' if session == '02' else ''}/"
        "scans/*/*/DICOM/files/*.dcm"
    )
    if output_root is None:
        return template, sources

    merged_scans = output_root / "source" / f"Smith-SRA-{folder_subject}" / "scans"
    if merged_scans.exists():
        raise ValueError(f"refusing to reuse merged source view: {merged_scans}")
    merged_scans.mkdir(parents=True)
    for source_index, (source, scan_dirs) in enumerate(inventories, start=1):
        source_relative = source.relative_to(source_root)
        for scan_index, scan_dir in enumerate(scan_dirs, start=1):
            alias = f"{source_index:02d}{scan_index:04d}-{_scan_label(scan_dir.name)}"
            target = Path("/sourcedata").joinpath(
                *source_relative.parts, "scans", scan_dir.name
            )
            os.symlink(target, merged_scans / alias)
    return template, sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("count", "prepare"):
        child = subparsers.add_parser(command)
        child.add_argument("--manifest", type=Path, required=True)
        child.add_argument("--subject", required=True)
        child.add_argument("--session", required=True)
        if command == "prepare":
            child.add_argument("--source-root", type=Path, required=True)
            child.add_argument("--output-root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        specs = load_supplemental_sources(args.manifest)
        matching = supplemental_sources_for(specs, args.subject, args.session)
        if args.command == "count":
            print(len(matching))
            return 0
        template, sources = prepare_merged_source(
            args.source_root,
            args.manifest,
            args.subject,
            args.session,
            args.output_root,
        )
        for source in sources:
            print(f"Including DICOM source: {source}", file=sys.stderr)
        print(template)
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
