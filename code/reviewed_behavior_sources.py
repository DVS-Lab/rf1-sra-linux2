"""Narrow, hash-bound source-label corrections; original files stay unchanged."""
import hashlib
from pathlib import Path


WAVE2_10964 = {
    "doors": ("doors", "1946ba20279a3cf1fb52bfbc320eceeba50f9c52bbec61dc6550d7d21461835f",
              "79b78ccf5265ce8fb3c12543a86c55758f24d62c2111ffb148822fbaa44c4f6d",
              "f47e0db595679100af9f771f630f8fd5c132691525986ca3d3fac3337f9321f4"),
    "socialdoors": ("faces", "e46d0abad17818c43af83f0aa31003134d2f6fb1ef1669d2c093ca89d3b9926b",
                    "f4ea65e4869099a92dc8a83cda9083144326c1b5e99dc95fa2f4d5a35cf1455b",
                    "1786ee8d17734862dd57ed49535c134ac0c0e44a87ccec0bd9104be1cd3e4d57"),
}


def wave2_source(root: Path, task: str) -> Path:
    raw, new_hash, old_hash, timing_hash = WAVE2_10964[task]
    directory = root / "Scan-Social_Doors/data/10964"
    stem = f"sub-10964_ses-01_task-socialReward_{raw}A3"
    source = directory / f"{stem}_events.tsv"
    files = [(source, new_hash),
             (directory / f"sub-10964_ses-1_task-socialReward_{raw}A3_events.tsv", old_hash),
             (directory / f"{stem}_desc-runtiming.jsonl", timing_hash)]
    for path, expected in files:
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"10964 reviewed {task} source contract changed; inspect privately")
    # A newly recovered correctly named file must not be silently ignored.
    if any(directory.glob(f"*ses-02*{raw}*_events.tsv")) or any(directory.glob(f"*ses-2_*{raw}*_events.tsv")):
        raise ValueError(f"10964 {task} now has a ses-02 candidate; reconcile before conversion")
    return source
