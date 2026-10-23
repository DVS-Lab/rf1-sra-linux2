from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import pause_tedana_cohort as pause


def test_pause_preserves_verified_success_and_identifies_only_partials(tmp_path, monkeypatch):
    rows = [{"run_key": "one"}, {"run_key": "two"}]
    monkeypatch.setattr(pause.cohort, "CONFIGS", ("nss-fastica",))
    def job(project, root, command, row, config):
        folder = root / "benchmark" / config / row["run_key"]
        return SimpleNamespace(output_dir=folder, run_key=row["run_key"], config=config)
    monkeypatch.setattr(pause.cohort, "job_for", job)
    complete = tmp_path / "benchmark/nss-fastica/one"
    complete.mkdir(parents=True)
    (complete / "cohort_success.json").write_text("{}")
    partial = tmp_path / "benchmark/nss-fastica/two"
    partial.mkdir()
    calls = []
    monkeypatch.setattr(pause.cohort, "cached_success", lambda j, v: calls.append(j.run_key))
    jobs, successes = pause.partial_jobs(tmp_path, tmp_path, {"rows": rows}, Path("tedana"), "26.0.3")
    assert successes == 1 and calls == ["one"] and [j.run_key for j in jobs] == ["two"]
    assert complete.is_dir() and partial.is_dir()


def test_bad_success_receipt_is_not_disposable_partial(tmp_path, monkeypatch):
    monkeypatch.setattr(pause.cohort, "CONFIGS", ("nss-fastica",))
    monkeypatch.setattr(pause.cohort, "job_for", lambda *a: SimpleNamespace(output_dir=tmp_path))
    (tmp_path / "cohort_success.json").write_text("{}")
    def fail(*args):
        raise ValueError("completion contract differs")
    monkeypatch.setattr(pause.cohort, "cached_success", fail)
    with pytest.raises(ValueError, match="contract differs"):
        pause.partial_jobs(tmp_path, tmp_path, {"rows": [{}]}, Path("tedana"), "26.0.3")


def test_exact_cohort_pid_contract_not_no_tedana_runner(monkeypatch, tmp_path):
    import os
    monkeypatch.setattr(pause.restart.os, "getsid", lambda _: 999)
    table = {100: dict(uid=os.getuid(), argv=["bash", "code/run_logged.sh"], sid=100, state="S", ppid=1),
             101: dict(uid=os.getuid(), argv=["python", "code/benchmark_tedana_cohort.py", "run", "--audit-root", str(tmp_path)], sid=100, state="S", ppid=100)}
    assert set(pause.restart.session_members(table, 101, tmp_path, "benchmark_tedana_cohort.py", "--audit-root")) == {100, 101}
    with pytest.raises(ValueError, match="requested Python"):
        pause.restart.session_members(table, 101, tmp_path)
    assert pause.find_runner(table, tmp_path) == 101
    assert pause.find_runner({100: table[100]}, tmp_path) is None
    with pytest.raises(ValueError, match="Multiple"):
        pause.find_runner({**table, 102: table[101]}, tmp_path)
