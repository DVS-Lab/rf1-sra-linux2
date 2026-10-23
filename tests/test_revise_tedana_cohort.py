from argparse import Namespace
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import revise_tedana_cohort as revision
from build_run_qc import RunKey


SOCIAL = "sub-11935_ses-01_task-socialdoors_run-1"
DOORS = revision.DOORS_KEY
OTHER = "sub-10001_ses-01_task-ugr_run-1"


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    def create(old_doors=False):
        project = tmp_path / "project"
        root = project / "derivatives/tedana-audit/cohort-pca-v1"
        root.mkdir(parents=True)
        excluded = tmp_path / "excluded"
        excluded.mkdir()
        archive = root / "revisions/v2"
        old_archive = tmp_path / "promotion/old-inputs"
        old_archive.mkdir(parents=True)
        keys = [RunKey("11935", "01", "socialdoors", "1"),
                RunKey("11935", "01", "doors", "1"), RunKey("10001", "01", "ugr", "1")]

        def make_row(key):
            names = [f"bids/{key.prefix}.nii.gz", f"bids/{key.prefix}.json"]
            for name in names:
                path = project / name
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_bytes(b"old image" if name.endswith(".gz") else b'{"old":true}')
            return {"subject": key.subject, "session": key.session, "task": key.task, "run": key.run,
                    "run_key": key.prefix, "number_of_original_volumes": 218, "nss_count": 0,
                    "inputs": {name: revision.cohort.signature(project / name) for name in names}}

        initial = [keys[0], keys[2]] + ([keys[1]] if old_doors else [])
        rows = [make_row(key) for key in initial]
        manifest = {"schema": 1, "project_root": str(project), "configs": list(revision.cohort.CONFIGS),
                    "source_excluded": ["99999"], "rows": rows, "blocked": []}
        # Unusual formatting verifies the old archive retains exact original bytes.
        other_literal = json.dumps(rows[1], indent=5)
        raw = json.dumps({k: v for k, v in manifest.items() if k != "rows"})[:-1]
        raw += ', "rows":[' + ",\n".join(other_literal if r["run_key"] == OTHER
                                           else json.dumps(r) for r in rows) + "]}\n"
        (root / "manifest.json").write_text(raw)
        for name in revision.RETIRED_FILES[1:]:
            (root / name).write_text("old " + name)
        (root / "progress.jsonl").write_text("historical progress\n")
        (root / "blocked.tsv").write_text("run_key\treason\n")
        old_inputs = {}
        for row in rows:
            if row["run_key"] not in revision.APPROVED_KEYS:
                continue
            for name, sig in row["inputs"].items():
                dest = old_archive / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(project / name, dest)
                old_inputs[name] = {"archive_path": name, **sig, "sha256": revision.cohort.sha256(dest)}

        def job_for(project, root, command, row, config):
            return Namespace(output_dir=root / "benchmark" / config / row["run_key"],
                             row=row, command=[str(command), config], project_root=project,
                             run_key=row["run_key"], config=config)

        monkeypatch.setattr(revision.cohort, "job_for", job_for)
        for row in rows:
            for config in revision.cohort.CONFIGS:
                job = job_for(project, root, Path("tedana"), row, config)
                job.output_dir.mkdir(parents=True)
                (job.output_dir / "result.tsv").write_text(row["run_key"] + config)
                saved = {"contract": revision.cohort.contract(job, "26.0.3"),
                         "outputs": revision.cohort.output_signatures(job)}
                (job.output_dir / "cohort_success.json").write_text(json.dumps(saved))
        # Canonical promotion already occurred; this helper never edits inputs.
        for key in keys[:2]:
            make_row(key)
            (project / f"bids/{key.prefix}.nii.gz").write_bytes(b"repaired image")
        current = {key.prefix: make_row(key) for key in keys}
        found = {key: [project / f"bids/{key.prefix}.nii.gz"] for key in keys}
        exclusions = {"99999"}
        calls = []

        def inspect(project, key, paths):
            calls.append(key.prefix)
            return copy.deepcopy(current[key.prefix])

        monkeypatch.setattr(revision.cohort, "inventory", lambda *_: (found, exclusions))
        monkeypatch.setattr(revision.cohort, "inspect_run", inspect)
        for record in old_inputs.values():
            record["archive_path"] = str(old_archive / record["archive_path"])
            record.pop("size")
            record.pop("mtime_ns")
        saved_manifest = tmp_path / "promotion/cohort/manifest.json"
        saved_manifest.parent.mkdir()
        shutil.copy2(root / "manifest.json", saved_manifest)
        info = {"source": str(root / "manifest.json"), "archive_path": str(saved_manifest),
                "sha256": hashlib.sha256(raw.encode()).hexdigest()}
        installs = [{"relpath": name, "sha256": revision.cohort.sha256(project / name)}
                    for key in revision.APPROVED_KEYS for name in current[key]["inputs"]]
        promotion = {"schema": 1, "project": str(project), "cohort_root": str(root),
                     "archive_root": str(tmp_path / "promotion"), "changed_keys": sorted(revision.APPROVED_KEYS),
                     "source_original_inputs": old_inputs, "installs": installs, "cohort_manifest": info}
        receipt = {"state": "installed", "plan": promotion,
                   **{k: promotion[k] for k in ("changed_keys", "source_original_inputs", "installs", "cohort_manifest")}}
        receipt_path = tmp_path / "promotion/promotion.json"
        receipt_path.write_text(json.dumps(receipt))
        (root / ".cohort.lock").touch()
        (project / ".11935-repair.lock").touch()
        return Namespace(project=project, root=root, archive=archive, excluded=excluded, old=manifest,
                         raw=raw.encode(), receipt=receipt, receipt_path=receipt_path,
                         current=current, found=found, exclusions=exclusions, calls=calls,
                         other_literal=other_literal)
    return create


def plan(exp):
    return revision.plan_revision(exp.project, exp.root, sorted(revision.APPROVED_KEYS), exp.archive,
                                  excluded_source_root=exp.excluded)


def snapshot(root):
    return {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_ino)
            for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("old_doors", [False, True])
def test_archive_and_addition_preserve_unrelated_receipts(experiment, old_doors):
    exp = experiment(old_doors)
    before = snapshot(exp.project)
    planned = plan(exp)
    assert snapshot(exp.project) == before  # planning even avoids creating the lock
    assert not exp.archive.exists()
    assert set(exp.calls) == revision.APPROVED_KEYS
    assert len([m for m in planned["moves"] if m["relative_path"].startswith("benchmark/")
                and m["snapshot"] is not None]) == (6 if old_doors else 3)
    provenance = revision.apply_revision(planned, promotion_receipt=exp.receipt_path)
    archived = exp.archive / "retired"
    assert (archived / "manifest.json").read_bytes() == exp.raw
    new = json.loads((exp.root / "manifest.json").read_text())
    assert new["schema"] == 1
    assert new["revision_provenance"] == provenance
    assert provenance["old_input_archive"] == exp.receipt["plan"]["archive_root"]
    assert len(new["rows"]) == 3
    assert {r["run_key"] for r in new["rows"]} == set(exp.current)
    assert next(r for r in new["rows"] if r["run_key"] == DOORS)["number_of_original_volumes"] == 218
    for row in exp.old["rows"]:
        for config in revision.cohort.CONFIGS:
            job = revision.cohort.job_for(exp.project, exp.root, Path("tedana"), row, config)
            if row["run_key"] in revision.APPROVED_KEYS:
                assert not job.output_dir.exists()
                assert (archived / job.output_dir.relative_to(exp.root) / "cohort_success.json").is_file()
            else:
                revision.cohort.cached_success(job, "26.0.3")
                assert new["rows"][1] == row
    for name in revision.RETIRED_FILES[1:]:
        assert not (exp.root / name).exists()
        assert (archived / name).read_bytes() == before[str((exp.root / name).relative_to(exp.project))][0]
    retired = {str((exp.root / m["relative_path"]).relative_to(exp.project)) for m in planned["moves"]}
    after = snapshot(exp.project)
    for name, value in before.items():
        if not any(name == path or name.startswith(path + "/") for path in retired):
            assert after[name] == value
    assert not (exp.root / revision.MARKER).exists()
    assert json.loads((exp.archive / "complete.json").read_text())["status"] == "complete"
    assert revision.cohort.load_manifest(Namespace(excluded_source_root=exp.excluded), exp.project, exp.root) == new
    with pytest.raises(ValueError, match="archive already exists"):
        revision.apply_revision(planned, promotion_receipt=exp.receipt_path)


def test_interruption_fails_closed_without_rearchiving(experiment, monkeypatch):
    exp = experiment()
    planned = plan(exp)
    rename = Path.rename

    def interrupted(source, dest):
        if source.name == "validation.json":
            raise OSError("simulated interruption")
        return rename(source, dest)

    monkeypatch.setattr(Path, "rename", interrupted)
    with pytest.raises(OSError, match="simulated interruption"):
        revision.apply_revision(planned, promotion_receipt=exp.receipt_path)
    assert (exp.root / revision.MARKER).is_file()
    assert (exp.archive / "retired/manifest.json").read_bytes() == exp.raw
    assert not (exp.root / "manifest.json").exists()
    before = snapshot(exp.project)
    with pytest.raises(ValueError, match="interrupted revision.*manual recovery"):
        revision.apply_revision(planned, promotion_receipt=exp.receipt_path)
    assert snapshot(exp.project) == before


def test_shared_active_lock_nonblocking(experiment):
    exp = experiment()
    planned = plan(exp)
    with revision.cohort.exclusive(exp.root):
        before = snapshot(exp.project)
        with pytest.raises(ValueError, match="another cohort command.*active"):
            revision.apply_revision(planned, promotion_receipt=exp.receipt_path)
        assert snapshot(exp.project) == before
    assert not exp.archive.exists()


@pytest.mark.parametrize("kind", ["repair-flock", "subject-mkdir"])
def test_production_lock_refused_and_not_cleared(experiment, kind):
    exp = experiment()
    planned = plan(exp)
    if kind == "repair-flock":
        with revision._flock(exp.project / ".11935-repair.lock"):
            with pytest.raises(ValueError, match="production repair is active"):
                revision.apply_revision(planned, promotion_receipt=exp.receipt_path)
    else:
        subject = exp.project / "logs/locks/fmriprep-sub-11935.lock"
        subject.mkdir(parents=True)
        with pytest.raises(ValueError, match="subject lock exists"):
            revision.apply_revision(planned, promotion_receipt=exp.receipt_path)
        assert subject.is_dir()
    assert not exp.archive.exists()
    assert (exp.root / "manifest.json").read_bytes() == exp.raw


def test_cli_postpromotion_default_archive(experiment, capsys):
    exp = experiment()
    args = ["--project-root", str(exp.project), "--audit-root", str(exp.root),
            "--promotion-receipt", str(exp.receipt_path), "--excluded-source-root", str(exp.excluded)]
    before = snapshot(exp.project)
    assert revision.main(["plan", *args]) == 0
    planned = json.loads(capsys.readouterr().out)
    assert Path(planned["archive_root"]) == exp.root / "revisions/promotion"
    assert snapshot(exp.project) == before
    assert revision.main(["apply", *args]) == 0
    provenance = json.loads(capsys.readouterr().out)
    assert Path(provenance["revision_archive"]).joinpath("complete.json").is_file()
    assert not (exp.project / "logs/locks/fmriprep-sub-11935.lock").exists()
    assert revision.main(["apply", *args]) == 1
    assert "archive already exists" in capsys.readouterr().err


def test_added_doors_existing_attempt_is_also_retired(experiment):
    exp = experiment()
    attempt = exp.root / "benchmark" / revision.cohort.CONFIGS[0] / DOORS
    attempt.mkdir(parents=True)
    (attempt / "partial.log").write_text("old unrecorded attempt")
    planned = plan(exp)
    revision.apply_revision(planned, promotion_receipt=exp.receipt_path)
    assert not attempt.exists()
    assert (exp.archive / "retired" / attempt.relative_to(exp.root) / "partial.log").read_text() == "old unrecorded attempt"


@pytest.mark.parametrize("change", ["other-input", "add-roster", "remove-roster", "exclusions",
                                  "wrong-keys", "no-old-target", "volume-count", "blocked"])
def test_inventory_invariants(experiment, change):
    exp = experiment()
    if change == "other-input":
        (exp.project / next(iter(exp.current[OTHER]["inputs"]))).write_bytes(b"changed")
    elif change == "add-roster":
        exp.found[RunKey("10002", "01", "ugr", "1")] = []
    elif change == "remove-roster":
        exp.found.pop(next(k for k in exp.found if k.prefix == OTHER))
    elif change == "exclusions":
        exp.exclusions.clear()
    elif change == "wrong-keys":
        with pytest.raises(ValueError, match="allowlist"):
            revision.plan_revision(exp.project, exp.root, [SOCIAL], exp.archive)
        return
    elif change == "no-old-target":
        exp.old["rows"] = [r for r in exp.old["rows"] if r["run_key"] == OTHER]
        (exp.root / "manifest.json").write_text(json.dumps(exp.old))
    elif change == "volume-count":
        exp.current[DOORS]["number_of_original_volumes"] = 217
    elif change == "blocked":
        exp.old["blocked"] = [{"run_key": "something", "reason": "blocked"}]
        (exp.root / "manifest.json").write_text(json.dumps(exp.old))
    before = snapshot(exp.project)
    with pytest.raises(ValueError):
        plan(exp)
    assert snapshot(exp.project) == before
    assert not exp.archive.exists()


@pytest.mark.parametrize("change", ["manifest", "output", "target-input", "plan"])
def test_stale_plan_rejected_before_archival(experiment, change):
    exp = experiment()
    planned = plan(exp)
    if change == "manifest":
        with (exp.root / "manifest.json").open("ab") as handle:
            handle.write(b" ")
    elif change == "output":
        next((exp.root / "benchmark").rglob("result.tsv")).write_text("changed output")
    elif change == "target-input":
        (exp.project / next(iter(exp.current[SOCIAL]["inputs"]))).write_bytes(b"changed")
    else:
        planned["refreshed_rows"][DOORS]["nss_count"] = 99
    with pytest.raises(ValueError, match="changed|mismatch"):
        revision.apply_revision(planned, promotion_receipt=exp.receipt_path)
    assert not exp.archive.exists()
    assert (exp.root / "manifest.json").is_file()


@pytest.mark.parametrize("change", ["not-promotion", "wrong-project", "not-complete", "old-manifest",
                                  "allowlist", "coverage", "hash", "bytes", "signature", "current"])
def test_promotion_receipt_and_old_byte_coverage(experiment, change):
    exp = experiment()
    planned = plan(exp)
    receipt = exp.receipt
    name = next(iter(receipt["source_original_inputs"]))
    record = receipt["source_original_inputs"][name]
    if change == "not-promotion":
        receipt["plan"]["schema"] = 99
    elif change == "wrong-project":
        receipt["plan"]["project"] = "/wrong-project"
    elif change == "not-complete":
        receipt["state"] = "applying"
    elif change == "old-manifest":
        receipt["cohort_manifest"]["sha256"] = "0" * 64
    elif change == "allowlist":
        receipt["changed_keys"] = [SOCIAL]
    elif change == "coverage":
        receipt["source_original_inputs"].pop(name)
    elif change == "hash":
        record["sha256"] = "0" * 64
    elif change == "bytes":
        saved = Path(record["archive_path"])
        before = saved.stat()
        saved.write_bytes(b"x" * before.st_size)
        os.utime(saved, ns=(before.st_mtime_ns, before.st_mtime_ns))
    elif change == "signature":
        saved = Path(record["archive_path"])
        before = saved.stat()
        os.utime(saved, ns=(before.st_mtime_ns + 1, before.st_mtime_ns + 1))
    else:
        receipt["installs"][0]["sha256"] = "0" * 64
    exp.receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        revision.apply_revision(planned, promotion_receipt=exp.receipt_path)
    assert not exp.archive.exists()
    assert not (exp.root / revision.MARKER).exists()
    assert (exp.root / "manifest.json").read_bytes() == exp.raw


@pytest.mark.parametrize("location", ["input", "output", "manifest", "audit-root", "archive-parent",
                                    "receipt", "old-input", "old-input-escape", "lock", "archive-escape"])
def test_path_escapes_and_symlinks(experiment, tmp_path, location):
    exp = experiment()
    planned = plan(exp)
    if location == "archive-escape":
        exp.archive = exp.root / "../escaped"
    elif location == "old-input-escape":
        next(iter(exp.receipt["source_original_inputs"].values()))["archive_path"] = str(exp.project / "bids/escaped")
        exp.receipt_path.write_text(json.dumps(exp.receipt))
    else:
        paths = {
            "input": exp.project / next(iter(exp.current[OTHER]["inputs"])),
            "output": exp.root / "benchmark" / revision.cohort.CONFIGS[0] / SOCIAL,
            "manifest": exp.root / "manifest.json", "audit-root": exp.root,
            "archive-parent": exp.archive.parent, "receipt": exp.receipt_path,
            "old-input": Path(next(iter(exp.receipt["source_original_inputs"].values()))["archive_path"]),
            "lock": exp.root / ".cohort.lock",
        }
        path = paths[location]
        target = tmp_path / "link-target"
        if path.exists():
            path.rename(target)
        else:
            target.mkdir()
        path.symlink_to(target, target_is_directory=target.is_dir())
    with pytest.raises(ValueError, match="symlink|escape"):
        if location in {"receipt", "old-input", "old-input-escape", "lock"}:
            revision.apply_revision(planned, promotion_receipt=exp.receipt_path)
        else:
            plan(exp)
    assert not exp.archive.exists()
