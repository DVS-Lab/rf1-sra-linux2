"""Read-only audit: preserve ambiguity, deduplicate echoes, redact metadata."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import audit_socdoors_sources as audit


def header(sop="sop1", series="private-series", echo="1", kind="M"):
    row = {key: "" for key in audit.TAGS}
    row.update(StudyInstanceUID="private-study", SeriesInstanceUID=series,
               SOPInstanceUID=sop, EchoNumbers=echo, SeriesNumber="20",
               ImageType=["ORIGINAL", kind], ProtocolName="SocialDoors_face PRIVATE",
               SeriesDescription="PRIVATE", TemporalPositionIdentifier="1",
               RepetitionTime="1615", NumberOfFrames="1")
    return row, 0


class AuditTests(unittest.TestCase):
    def test_fixed_label_vocabulary_and_numeric_redaction(self):
        self.assertEqual(audit.hint("SocialDoors_face PRIVATE"), "socialdoors")
        self.assertEqual(audit.hint("SocialDoors_doors"), "doors")
        self.assertEqual(audit.hint("SECRET unknown sequence"), "other")
        self.assertEqual(audit.numeric("PRIVATE"), "unknown")
        self.assertEqual(audit.series_number("20-PRIVATE"), "20")

    def test_echo_counts_deduplicate_without_merging_series(self):
        rows = {"a": header(), "copy": header(), "b": header(sop="sop2", echo="2"),
                "phase": header(sop="sop3", series="phase-series", kind="P")}
        groups, errors = audit.collect_headers([Path(k) for k in rows], lambda p: rows[p.name])
        self.assertFalse(errors)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["echoes"], {"1": 1, "2": 1})
        self.assertEqual(groups[0]["duplicates"], 1)
        self.assertEqual(groups[0]["positions"]["1"], {"1"})

    def test_identity_conflict_is_an_error_not_silent_deduplication(self):
        rows = {"a": header(), "bad": header(series="other-series")}
        _, errors = audit.collect_headers([Path(k) for k in rows], lambda p: rows[p.name])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["error_type"], "ValueError")

    def test_public_header_report_redacts_and_qualifies_counts(self):
        groups, errors = audit.collect_headers([Path("private-file")], lambda p: header())
        out = io.StringIO()
        with redirect_stdout(out):
            audit.header_report("11171", groups, errors)
        report = out.getvalue()
        for secret in ("PRIVATE", "private-file", "private-study", "private-series", "sop1"):
            self.assertNotIn(secret, report)
        self.assertIn("socialdoors | magnitude | 1:1", report)
        self.assertIn("NOT volume counts", report)
        self.assertIn("do not prove complete", report)

    def test_unreadable_header_reports_type_not_private_message(self):
        def reader(path):
            raise ValueError("PRIVATE PATIENT INFORMATION")
        _, errors = audit.collect_headers([Path("private-file")], reader)
        self.assertEqual(errors, [{"path": "private-file", "error_type": "ValueError"}])

    def test_behavior_report_contains_no_source_path_or_detail(self):
        from types import SimpleNamespace
        out = io.StringIO()
        source = SimpleNamespace(status="available", detail="PRIVATE", path=Path("private-path"))
        converted = SimpleNamespace(trial_count=1, source_sha256="hash",
                                    rows=[dict(onset=0, duration=5.19, trial_type="decision-missed")])
        with patch.object(audit, "SUBJECTS", ["11203"]), \
             patch.object(audit, "resolve_sources", return_value={1: source}), \
             patch.object(audit, "convert_source", return_value=converted), redirect_stdout(out):
            records, errors = audit.behavioral_report(Path("private-root"))
        self.assertEqual(errors, 0)
        self.assertEqual(records[0]["last_end"], 5.19)
        self.assertIn("| 1 | 1 | 5.190", out.getvalue())
        self.assertNotIn("PRIVATE", out.getvalue())
        self.assertNotIn("private-path", out.getvalue())


if __name__ == "__main__":
    unittest.main()
