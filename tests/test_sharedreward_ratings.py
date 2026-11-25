"""Wave, source, scoring and preservation checks for the post-task ratings."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import sharedreward_ratings as sr


HEADER = "TrialNumber,Partner,Trait,ran,order,Rating\n"


def attempt(scores):
    cells = [(p, t) for t in (0, 1) for p in (3, 2, 1)]
    return HEADER + "".join(f"{i},{p},{t},1.0,{i-1}.0,{s}\n"
                            for i, ((p, t), s) in enumerate(zip(cells, scores), 1))


def test_order_direction_and_repeated_header():
    raw = "\ufeff" + attempt([0] * 6) + "\ufeff" + attempt([5, 3, 1, -4, -1, 0])
    blocks = sr.read_attempts(raw.encode())
    assert sr.selected_block(blocks) == 1
    selected = blocks[1]
    assert [i["trial_number"] for i in selected] == list(range(1, 7))
    row = sr.model_row("sub-10000", selected, True)
    assert [row[key] for key in sr.CELLS] == [5, -4, 3, -1, 1, 0]
    assert [row[key] for key in ("friend_win_minus_loss", "X_FS", "X_FC")] == [9, 5, 8]
    assert row["ratings_qc_pass"] == "true"


def test_incomplete_attempts_and_observed_zeros():
    blocks = sr.read_attempts((attempt([0, 3, 2, 0, -1, -2]) + attempt([5, 2])).encode())
    assert sr.selected_block(blocks) == 0
    assert sr.model_row("sub-10001", blocks[0], True)["ratings_qc_pass"] == "true"
    partial = sr.model_row("sub-10001", blocks[1], True)
    assert (partial["friend_win"], partial["friend_loss"], partial["X_FS"]) == (5, sr.NA, sr.NA)
    assert (partial["ratings_status"], partial["ratings_qc_pass"]) == ("partial", "false")
    assert sr.model_row("sub-10001", [], False)["ratings_status"] == "missing_source"


@pytest.mark.parametrize("scores,reason", [([4] * 6, "all_six_identical"),
                                         ([0, 4, 2, 1, -3, -1], "friend_loss_gt_win")])
def test_qc_flags_keep_raw_data(scores, reason):
    items = sr.read_attempts(attempt(scores).encode())[0]
    result = sr.model_row("sub-10002", items, True)
    assert (result["ratings_status"], result["ratings_qc_reason"]) == ("complete", reason)
    assert result["friend_loss"] == scores[3]


@pytest.mark.parametrize("data", [attempt([6]), attempt(["inf"]), attempt([2.5]),
                                  attempt([1, 2]).replace("2,2,0", "2,3,0")])
def test_malformed_sources_are_not_exported(data):
    with pytest.raises(ValueError):
        sr.read_attempts(data.encode())


def test_only_reviewed_multi_file_case_is_automatic():
    names = [f"logs/10369/sub10369_SR-Ratings-{x}.csv" for x in (1, 2)]
    assert sr.select_file("sub-10369", names) == names[1]
    with pytest.raises(ValueError, match="Multiple ratings"):
        sr.select_file("sub-10003", names)


def test_pinned_git_export_and_prepublished_files(tmp_path):
    from types import SimpleNamespace

    raw, bids, omitted = (tmp_path / s for s in ("rf1-sra", "bids", "exclusions"))
    for p in (raw, bids, omitted):
        p.mkdir()
    sr.git(raw, "init", "--quiet")
    for sub in ("10001", "10002", "10003", "999"):
        dest = raw / sr.LOGS / sub / f"sub{sub}_SR-Ratings-1.csv"
        dest.parent.mkdir(parents=True)
        dest.write_text(attempt([5, 3, 2, -2, -1, -1]))
    sr.git(raw, "add", "stimuli")
    sr.git(raw, "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
           "commit", "--quiet", "-m", "Wave 1")
    (raw / sr.LOGS / "10001/sub10001_SR-Ratings-1.csv").write_text(attempt([0] * 6))
    (omitted / "Smith-SRA-10003").mkdir()
    (bids / "participants.tsv").write_text("participant_id\nsub-10001\nsub-10004\n")
    args = SimpleNamespace(bids_root=bids, output_dir=tmp_path / "derivatives", source_repo=raw,
                           source_ref="HEAD", exclusions_root=omitted, local_snapshot=False,
                           apply=False, check=False)
    sr.run(args)
    assert not args.output_dir.exists()
    args.apply = True
    sr.run(args)
    args.apply, args.check = False, True
    sr.run(args)
    results = list(bids.rglob("*_beh.tsv"))
    assert len(results) == 1 and "friend\twin\t5" in results[0].read_text()
    sources = (args.output_dir / "sources.tsv").read_text()
    assert "10003" not in sources and "unlinked_to_roster" in sources
    counts = json.loads((args.output_dir / "provenance.json").read_text())["counts"]
    assert counts["statuses"] == {"complete": 1, "missing_source": 1}
    results[0].write_text("manually changed")
    args.apply, args.check = True, False
    with pytest.raises(ValueError, match="Existing output differs"):
        sr.run(args)
    assert results[0].read_text() == "manually changed"
