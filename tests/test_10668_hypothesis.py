"""Parameter comparisons must distinguish missing evidence from equality."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from audit_10668_hypothesis import compare_parameters


class ParameterTests(unittest.TestCase):
    def test_same_different_incomplete_and_unavailable(self):
        records = []
        for task, run in (("trust", 1), ("trust", 2), ("sharedreward", 1)):
            records.append({"path": f"sub-10668_ses-01_task-{task}_run-{run}_echo-1_part-mag_bold.json",
                            "metadata": {"RepetitionTime": 1.615, "EchoTime": 0.0138,
                                         "ReceiveCoilName": "PRIVATE-COIL"}})
        records[2]["metadata"]["EchoTime"] = 0.015
        records[2]["metadata"]["FlipAngle"] = 60
        results = compare_parameters({"bids_sidecars": records})
        first = {r["parameter"]: r["status"] for r in results if r["echo"] == 1}
        self.assertEqual(first["RepetitionTime"], "equal")
        self.assertEqual(first["EchoTime"], "different")
        self.assertEqual(first["FlipAngle"], "incomplete")
        self.assertEqual(first["SliceTiming"], "unavailable")
        self.assertNotIn("PRIVATE-COIL", str(results))

    def test_duplicate_sidecar_not_arbitrarily_selected(self):
        entry = {"path": "sub-10668_ses-01_task-trust_run-1_echo-1_part-mag_bold.json",
                 "metadata": {"RepetitionTime": 1.615}}
        results = compare_parameters({"bids_sidecars": [entry, entry]})
        self.assertTrue(all(r["status"] == "unavailable" for r in results))


if __name__ == "__main__":
    unittest.main()
