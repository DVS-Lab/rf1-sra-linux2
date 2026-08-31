#!/usr/bin/env python3
"""HeuDiConv grouping for reviewed multi-visit, single-session inputs."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable


SCAN_ALIAS = re.compile(r"^(?P<source>\d{2})\d{4}-")


def _source_index(filename: str) -> int:
    parts = Path(filename).parts
    scan_name = next(
        (parts[index + 1] for index, part in enumerate(parts[:-1]) if part == "scans"),
        "",
    )
    match = SCAN_ALIAS.match(scan_name)
    if match is None:
        raise RuntimeError(
            "reviewed multi-source DICOM path lacks a source-prefixed scan alias: "
            f"{filename}"
        )
    return int(match.group("source"))


def group_multi_source_session(
    files: list[str],
    dcmfilter: Callable[[Any], Any] | None,
    seqinfo_type: type,
) -> dict[Any, list[str]]:
    """Group each source visit separately, then assign collision-free series IDs."""
    del seqinfo_type  # Required by HeuDiConv's custom-grouping callable API.
    by_source: dict[int, list[str]] = defaultdict(list)
    for filename in files:
        by_source[_source_index(filename)].append(filename)

    from heudiconv.dicoms import group_dicoms_into_seqinfos

    combined: dict[Any, list[str]] = {}
    for source_index in sorted(by_source):
        grouped = group_dicoms_into_seqinfos(
            sorted(by_source[source_index]),
            "studyUID",
            dcmfilter=dcmfilter,
            flatten=True,
        )
        for seqinfo, series_files in grouped.items():
            number, separator, description = seqinfo.series_id.partition("-")
            if not separator or not number.isdigit():
                raise RuntimeError(
                    f"unexpected HeuDiConv series identifier: {seqinfo.series_id!r}"
                )
            unique_number = source_index * 1_000_000 + int(number)
            unique_seqinfo = seqinfo._replace(
                series_id=f"{unique_number}-{description}"
            )
            if unique_seqinfo in combined:
                raise RuntimeError(
                    f"duplicate grouped sequence after source disambiguation: {unique_seqinfo}"
                )
            combined[unique_seqinfo] = series_files
    return combined
