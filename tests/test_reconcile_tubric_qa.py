import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "reconcile_tubric_qa", Path(__file__).resolve().parents[1] / "code/reconcile_tubric_qa.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class ReconciliationTests(unittest.TestCase):
    def test_exact_compression_pair_does_not_change_files(self):
        with tempfile.TemporaryDirectory() as directory:
            plain = Path(directory) / "T1w.nii"
            compressed = Path(directory) / "T1w.nii.gz"
            payload = b"header and voxel bytes" * 1000
            plain.write_bytes(payload)
            compressed.write_bytes(gzip.compress(payload))
            original = compressed.read_bytes()
            result = audit.compare_pair(plain, compressed)
            self.assertEqual(result["status"], "identical_uncompressed_bytes")
            self.assertEqual(plain.read_bytes(), payload)
            self.assertEqual(compressed.read_bytes(), original)

    def test_different_and_corrupt_compression(self):
        with tempfile.TemporaryDirectory() as directory:
            plain = Path(directory) / "T1w.nii"
            compressed = Path(directory) / "T1w.nii.gz"
            plain.write_bytes(b"one")
            compressed.write_bytes(gzip.compress(b"two"))
            self.assertEqual(audit.compare_pair(plain, compressed)["status"], "different_contents")
            compressed.write_bytes(b"invalid gzip")
            with self.assertRaises(OSError):
                audit.compare_pair(plain, compressed)

    def test_metric_comparison_exact_match_missing_and_different(self):
        canonical = [{"bids_bold": "bids/sub-x/task-rest_bold.nii.gz", "tsnr": "30", "fd_mean": "0.1"}]
        scanner = [{"bids_sidecar": "bids/sub-x/task-rest_bold.json", "fwhm_avg_mm": "6"}]
        portable = [{"image_id": "sub-x/task-rest_bold.nii.gz", "tsnr": "30", "fd_mean": "0.1", "fwhm_mean_mm": "6"}]
        self.assertEqual(audit.compare_metrics(canonical, portable, scanner), [])
        portable[0]["tsnr"] = "31"
        self.assertEqual(len(audit.compare_metrics(canonical, portable, scanner)), 1)
        self.assertEqual(len(audit.compare_metrics(canonical, [], scanner)), 3)
        portable[0]["tsnr"] = "n/a"
        self.assertEqual(len(audit.compare_metrics(canonical, portable, scanner)), 1)

    def test_report_integrity_and_unsafe_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            file = root / "run_qc.tsv"
            file.write_text("original")
            manifest = root / "provenance.json"
            manifest.write_text(json.dumps({"outputs": {"run_qc.tsv": audit.digest(file)["sha256"]}}))
            audit.verify_report(root)
            file.write_text("modified")
            with self.assertRaisesRegex(ValueError, "changed"):
                audit.verify_report(root)
            manifest.write_text(json.dumps({"outputs": {"../escape": "unused"}}))
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                audit.verify_report(root)


if __name__ == "__main__":
    unittest.main()
