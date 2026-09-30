"""Synthetic checks for the reviewed acquisition swap and immutable originals."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import nibabel as nib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import repair_10668 as r


def image(path, n, value):
    data = np.full((2, 3, 4, n), value, dtype=np.int16)
    data[..., -1] = value + 3
    img = nib.Nifti1Image(data, np.diag([2.7, 2.7, 2.97, 1]))
    img.header.set_zooms((2.7, 2.7, 2.97, 1.615))
    img.header.set_xyzt_units("mm", "sec")
    img.set_qform(img.affine, 1)
    img.set_sform(img.affine, 2)
    img.header.set_slope_inter(0.5, 4)
    nib.save(img, path)


def fixture(root):
    bids = root / "bids"
    session = bids / r.SESSION
    func = session / "func"
    func.mkdir(parents=True)
    files = []
    for old, n, v, series in ((r.OLD_A, 280, 10, 11), (r.OLD_B, 255, 20, 14)):
        for part, number in (("mag", series), ("phase", series + 1)):
            for echo in range(1, 5):
                stem = f"{old}_echo-{echo}_part-{part}_bold"
                image(func / (stem + ".nii.gz"), n, v)
                meta = {"TaskName": "trust" if old == r.OLD_A else "sharedreward",
                        "SeriesNumber": number, "RepetitionTime": 1.615,
                        "EchoTime": [0.0138, 0.03154, 0.04928, 0.06702][echo - 1]}
                (func / (stem + ".json")).write_text(json.dumps(meta))
        image(func / (old + "_sbref.nii.gz"), 1, v)
        (func / (old + "_sbref.json")).write_text(json.dumps({"SeriesNumber": series - 1}))
        (func / (old + "_events.tsv")).write_text("old events\n")
        files.extend(str(p.relative_to(session)) for p in func.glob(old + "_*"))
    (func / "unrelated.txt").write_text("untouched")
    (func / f"{r.PREFIX}task-trust_run-1_echo-1_part-mag_bold.json").write_text('{"SeriesNumber": 8}')
    (session / "fmap").mkdir()
    (session / "fmap/old.json").write_text("{}")
    (session / (r.PREFIX + "scans.tsv")).write_text("filename\tacq_time\n" + "".join(
        f"{p}\tprivate-original-time\n" for p in files if p.endswith(".nii.gz")))
    return bids, files


def events(_sub, _ses, _tasks, _behavior, bids, **kwargs):
    for run in (1, 2):
        (bids / r.SESSION / "func" / f"{r.PREFIX}task-sharedreward_run-{run}_events.tsv").write_text(f"attempt-{run}\n")
    return 0


class RepairTests(unittest.TestCase):
    def validate(self, bids, inv):
        def link(_bids, _sub, run, _meta, _series, task="sharedreward", **kwargs):
            num = "14" if task == "sharedreward" else "8" if run == "1" else "11"
            return "PROVENANCE_UID_LINKED", [{"fields": {"SeriesNumber": [num]}, "folders": ["10668"]}], [], {}
        with patch.object(r, "INVENTORY_SHA", r.sha(inv)), patch.object(r, "behavior_check"), patch.object(r, "conversion_match", side_effect=link):
            return r.validate_original(bids, inv, inv.parent)

    def test_preflight_rejects_conflicts_parameters_and_lengths(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bids, files = fixture(root)
            inv = root / "inv.json"
            inv.write_text('{"series": []}')
            self.assertEqual(set(self.validate(bids, inv)), set(files))
            target = bids / r.SESSION / "func" / (r.NEW_B + "_events.tsv")
            target.write_text("conflict")
            with self.assertRaises(r.RepairError):
                self.validate(bids, inv)
            target.unlink()
            path = bids / r.SESSION / "func" / (r.OLD_A + "_echo-1_part-mag_bold.nii.gz")
            image(path, 279, 10)
            with self.assertRaises(r.RepairError):
                self.validate(bids, inv)

    def test_changed_inventory_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inv = root / "inv.json"
            inv.write_text("{}")
            with self.assertRaises(r.RepairError):
                r.validate_original(root, inv, root)

    def test_mapping_is_simultaneous(self):
        self.assertEqual(r.renamed([r.OLD_A, r.OLD_B]), [r.NEW_A, r.NEW_B])

    def test_stage_preserves_sources_and_exact_crop(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bids, files = fixture(root)
            before = r.tree_hashes(bids / r.SESSION)
            with patch.object(r, "convert_behavior", side_effect=events):
                target = r.build_stage(bids, root / "stage", files, root)
            self.assertEqual(before, r.tree_hashes(bids / r.SESSION))
            r.check_session(target)
            self.assertFalse((target / "fmap").exists())
            self.assertEqual((target / "func/unrelated.txt").read_text(), "untouched")
            for old, new in ((r.OLD_A, r.NEW_A), (r.OLD_B, r.NEW_B)):
                name = "_echo-1_part-mag_bold.nii.gz"
                src = nib.load(bids / r.SESSION / "func" / (old + name))
                dst = nib.load(target / "func" / (new + name))
                np.testing.assert_array_equal(np.asanyarray(src.dataobj)[..., :255], np.asanyarray(dst.dataobj))
                self.assertEqual(dst.header["qform_code"], 1)
                self.assertEqual(dst.header["sform_code"], 2)
            self.assertNotIn(r.OLD_A, (target / (r.PREFIX + "scans.tsv")).read_text())

    def test_live_archive_check_and_idempotency(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bids, files = fixture(root)
            info = bids / ".heudiconv/10668/ses-01"
            info.mkdir(parents=True)
            (info / "saved.txt").write_text("conversion provenance")
            deriv = root / "derivatives/fmriprep/sub-10668"
            deriv.mkdir(parents=True)
            (deriv / "old.txt").write_text("old derivative")
            inv = root / "inventory.json"
            inv.write_text("{}")
            with patch.object(r, "validate_original", return_value=files), patch.object(r, "convert_behavior", side_effect=events):
                r.apply_live(root, inv, root, False)
                self.assertFalse((root / "derivatives/source_repairs").exists())
                r.apply_live(root, inv, root, True)
                r.apply_live(root, inv, root, True)
            self.assertFalse(deriv.exists())
            archive = root / "derivatives/source_repairs" / r.ID
            self.assertTrue((archive / "original_session/func" / (r.OLD_A + "_sbref.nii.gz")).exists())
            self.assertEqual((archive / "retired/derivatives/fmriprep/sub-10668/old.txt").read_text(), "old derivative")
            (bids / r.SESSION / "func/unrelated.txt").write_text("changed")
            with self.assertRaises(r.RepairError):
                r.apply_live(root, inv, root, False)

    def test_interrupted_receipt_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            r.write_json(root / "derivatives/source_repairs" / r.ID / "receipt.json", {"status": "installing"})
            with self.assertRaises(r.RepairError):
                r.apply_live(root, root, root, True)


if __name__ == "__main__":
    unittest.main()
