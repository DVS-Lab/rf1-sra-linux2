"""PI-approved 11935 ses-01 mapping; only selected by prepdata for that visit."""
import re

from heuristics_XA30 import filter_files, grouping, POPULATE_INTENDED_FOR_OPTS
from heuristics_XA30 import infotodict as base_mapping


def infotodict(seqinfo):
    info = base_mapping(seqinfo)
    by_number = {}
    for item in seqinfo:
        match = re.match(r"^(\d+)-", str(item.series_id))
        if match:
            by_number.setdefault(int(match[1]), []).append(item)
    expected = {23: (4, False), 24: (4, True), 25: (872, False), 26: (872, True),
                27: (4, False), 28: (4, True), 29: (872, False), 30: (872, True)}
    for number, (frames, phase) in expected.items():
        candidates = by_number.get(number, [])
        if len(candidates) != 1:
            raise ValueError(f"11935 reviewed series {number} missing or ambiguous")
        item = candidates[0]
        description = item.series_description
        if (item.dim4 != frames or "SocialDoors_face" not in description or
                ("_Pha" in description) != phase or ("SBRef" in description) != (frames == 4)):
            raise ValueError(f"11935 reviewed series {number} role/length differs")
    for key in info:
        for task, first in (("socialdoors", 25), ("doors", 29)):
            if f"_task-{task}_" not in key[0]:
                continue
            number = first - 2 if key[0].endswith("_sbref") else first + int("_part-phase_" in key[0])
            info[key] = [by_number[number][0].series_id]
    return info
