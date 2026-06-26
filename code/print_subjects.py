#!/usr/bin/env python3
"""Print normalized subject IDs from a subject list."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_utils import read_subject_list


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subject_list", type=Path)
    args = parser.parse_args()
    for subject in read_subject_list(args.subject_list):
        print(subject)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
