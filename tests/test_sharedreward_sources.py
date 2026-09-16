"""Source audit must preserve ambiguity and keep identifying fields private."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from audit_sharedreward_sources import (TAGS, clock_seconds, collect_series,
                                       event_segments, public_report, read_header,
                                       timestamp)
import audit_sharedreward_sources as audit


def record(study="1.2.3", series="1.2.3.4", sop="1.2.3.4.1", when="20230926120000", echo="1"):
    r = {k: "" for k in TAGS}
    r.update(StudyInstanceUID=study, SeriesInstanceUID=series, SOPInstanceUID=sop,
             PatientID="PRIVATE-ID", SeriesNumber="42", EchoNumbers=echo,
             AcquisitionDateTime=when, ProtocolName="SharedReward PRIVATE-NAME",
             ImageType=["ORIGINAL", "PRIMARY", "M", "NORM"])
    return r


class SourceAuditTests(unittest.TestCase):
    def test_series_identity_duplicates_and_echoes(self):
        records = {"a": record(), "copy": record(),
                   "echo2": record(sop="1.2.3.4.2", echo="2"),
                   "second": record(study="2.3.4", series="2.3.4.5", sop="2.3.4.5.1")}
        series, errors = collect_series([("10668", Path(k)) for k in records], lambda p: records[p.name])
        self.assertFalse(errors)
        self.assertEqual(len(series), 2)  # Same series number, different studies.
        self.assertEqual(series[0]["headers"], 2)  # Echoes are not separate runs.
        self.assertEqual(series[0]["duplicate_files"], 1)
        self.assertEqual(series[0]["fields"]["EchoNumbers"], {"1", "2"})

    def test_public_report_redacts_private_values_and_preserves_relative_order(self):
        records = {"a": record(), "b": record(series="1.2.3.5", sop="1.2.3.5.1", when="20230926121000")}
        series, errors = collect_series([("10668", Path(k)) for k in records], lambda p: records[p.name])
        text = public_report(series, [], [], errors, [], b"test-key")
        for forbidden in ["PRIVATE", "1.2.3", "20230926", "121000"]:
            self.assertNotIn(forbidden, text)
        self.assertIn("600.000/600.000", text)
        self.assertIn("not acquisition counts", text)

    def test_duplicate_registration_difference_is_preserved(self):
        records = {"a": record(), "copy": record()}
        records["copy"]["PatientID"] = "DIFFERENT-REGISTRATION"
        series, errors = collect_series([("10668", Path(k)) for k in records], lambda p: records[p.name])
        self.assertFalse(errors)
        self.assertEqual(series[0]["fields"]["PatientID"], {"PRIVATE-ID", "DIFFERENT-REGISTRATION"})
        self.assertEqual(series[0]["headers"], 1)

    def test_repeated_header_retains_attempts_not_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            header = ["Trialn", "Partner", "Feedback", "decision_onset"]
            content = io.StringIO()
            csv.writer(content).writerows([header, [1, 3, 1, 4.1], header, [1, 3, 1, 4.2]])
            path = Path(tmp) / "source.csv"
            path.write_text(content.getvalue(), encoding="utf-8-sig")
            segments = event_segments(path)["segments"]
            self.assertEqual([s["rows"] for s in segments], [1, 1])
            self.assertEqual(segments[0]["design_sha256"], segments[1]["design_sha256"])
            self.assertNotEqual(segments[0]["timing_sha256"], segments[1]["timing_sha256"])

    def test_missing_acquisition_time_not_replaced_with_study_date(self):
        r = record(when="")
        r["StudyDate"] = "20230926"
        self.assertEqual(timestamp(r), "")
        r.update(AcquisitionDate="20230926", AcquisitionTime="120000.25")
        self.assertEqual(timestamp(r), "20230926120000.25")
        self.assertEqual(clock_seconds("20230926120000.25-0400"), 43200.25)

    def test_real_dicom_header_without_pixels(self):
        try:
            import pydicom
        except ImportError:
            self.skipTest("pydicom unavailable")
        from pydicom.dataset import FileDataset, FileMetaDataset
        with tempfile.TemporaryDirectory() as tmp:
            meta = FileMetaDataset()
            meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
            path = Path(tmp) / "test.dcm"
            ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
            for k, v in record().items():
                if v:
                    setattr(ds, k, v)
            ds.save_as(path)
            header = read_header(path)
            self.assertEqual(header["SeriesInstanceUID"], "1.2.3.4")
            self.assertEqual(header["ImageType"], ["ORIGINAL", "PRIMARY", "M", "NORM"])

    def test_bad_header_recorded_without_exception_text(self):
        def fail(_):
            raise ValueError("PRIVATE-NAME")
        series, errors = collect_series([("10668", Path("private.dcm"))], fail)
        self.assertFalse(series)
        self.assertEqual(errors[0]["error_type"], "ValueError")
        self.assertNotIn("PRIVATE-NAME", json.dumps(errors))

    def test_end_to_end_private_output_and_no_source_edits(self):
        try:
            import nibabel as nib
            import numpy as np
            import pydicom
        except ImportError:
            self.skipTest("imaging dependencies unavailable")
        from pydicom.dataset import FileDataset, FileMetaDataset
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            bids = root / "bids"
            behavior = root / "behavior"
            for n, subject in enumerate(audit.SUBJECTS, 1):
                path = source / f"Smith-SRA-{subject}" / "scans" / "image.dcm"
                path.parent.mkdir(parents=True)
                meta = FileMetaDataset()
                meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
                ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
                for k, v in record(study=f"1.2.{n}", series=f"1.2.{n}.1", sop=f"1.2.{n}.1.1").items():
                    if v:
                        setattr(ds, k, v)
                ds.save_as(path)
                func = bids / f"sub-{subject}" / "ses-01" / "func"
                func.mkdir(parents=True)
                stem = f"sub-{subject}_ses-01_task-sharedreward_run-1_echo-1_part-mag_bold"
                image = nib.Nifti1Image(np.zeros((2, 2, 2, 4), dtype=np.float32), np.eye(4))
                image.header.set_xyzt_units("mm", "sec")
                nib.save(image, func / f"{stem}.nii.gz")
                (func / f"{stem}.json").write_text('{"RepetitionTime": 1, "PrivateTest": "PRIVATE-NAME"}')
            logs = behavior / "Scan-Card_Guessing_Game/logs/10668"
            logs.mkdir(parents=True)
            content = "Trialn,Partner,Feedback,decision_onset\n1,3,1,4\n"
            for name in ["sub-10668_task-sharedreward_run-1_raw.csv", "sub-10668_task-sharedreward_run-2_raw.csv", "sub-10668_task-sharedreward_run-1_raw.csv~"]:
                (logs / name).write_text(content)
            before = {p: p.read_bytes() for base in [source, bids, behavior] for p in base.rglob("*") if p.is_file()}
            args = SimpleNamespace(source_root=source, bids_root=bids,
                                   behavior_root=behavior, private_output=root / "work" / "audit")
            out = io.StringIO()
            with patch.object(audit, "ROOT", root), redirect_stdout(out):
                self.assertEqual(audit.run(args), 0)
                with self.assertRaises(ValueError):
                    audit.run(args)  # No overwriting an existing audit.
                args.private_output = root / "logs" / "unsafe"
                with self.assertRaises(ValueError):
                    audit.run(args)  # Private fields cannot go to tracked logs.
            self.assertNotIn("PRIVATE-NAME", out.getvalue())
            self.assertIn("CHECK PASSED: inventory collected", out.getvalue())
            for path, original in before.items():
                self.assertEqual(path.read_bytes(), original)
            inventory = root / "work/audit/inventory.json"
            self.assertEqual(inventory.stat().st_mode & 0o777, 0o600)
            self.assertEqual(inventory.parent.stat().st_mode & 0o777, 0o700)
            self.assertIn("PRIVATE-NAME", inventory.read_text())


if __name__ == "__main__":
    unittest.main()
