#!/usr/bin/env python3
"""Read-only Siemens header sampling; all header values stay in ignored work/."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import warnings

ERAS = ("E11", "XA30", "XA60")
TASKS = ("doors", "socialdoors", "sharedreward", "trust", "ugr")
NAME = re.compile(
    r"sub-(\d+)_ses-(\d+)_task-(doors|socialdoors|sharedreward|trust|ugr)"
    r"_run-(\d+)_echo-1(?:_part-mag)?_bold\.json$")
INTEREST = re.compile(
    r"filter|smooth|interp|recon|distort|gradient|coil|spat\.|kspace|"
    r"sliceaccel|partialfourier|sliceorder|unwarp|denois|normalize|prescan", re.I)
STANDARD = {
    "RepetitionTime", "EchoTime", "EffectiveEchoTime", "FlipAngle",
    "SliceThickness", "SpacingBetweenSlices", "PixelSpacing", "PixelBandwidth",
    "ParallelReductionFactorInPlane", "PartialFourier", "KSpaceFiltering",
    "VolumetricProperties", "ImageType", "ComplexImageComponent", "FrameType",
    "ReceiveCoilName", "SoftwareVersions", "ScanOptions", "AcquisitionMatrix",
    "Rows", "Columns", "NumberOfFrames", "PulseSequenceName",
}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def era(value):
    return next((item for item in ERAS if item in str(value).upper()), "unknown")


def flatten(value, prefix):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from flatten(item, f"{prefix}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from flatten(item, f"{prefix}[{index}]")
    else:
        yield prefix, value


def parse_protocol(block, parser):
    # Siemens emits array declarations before indexed values. NiBabel otherwise
    # constructs a dict for the declaration and then cannot turn it into a list.
    declarations, lines = [], []
    for line in block.splitlines():
        lhs = line.split("=", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_][\w.\[\]]*\.__attribute__\.[A-Za-z_]\w*", lhs):
            declarations.append(line)
        else:
            lines.append(line)
    errors = []
    for delimiter in ('"', '""'):
        try:
            parsed, attributes = parser("\n".join(lines), str_delim=delimiter)
            return parsed, attributes, declarations
        except Exception as exc:
            errors.append(type(exc).__name__)
    raise ValueError("ASCCONV decode failed: " + ",".join(errors))


def select_samples(bids, sessions, eras, count):
    groups = defaultdict(list)
    for path in sorted(bids.glob("sub-*/ses-*/func/*_echo-1*bold.json")):
        match = NAME.fullmatch(path.name)
        if not match:
            continue
        subject, session, task, run = match.groups()
        if session not in sessions:
            continue
        payload = json.loads(path.read_text())
        version = era(payload.get("SoftwareVersions", ""))
        if version not in eras:
            continue
        groups[task, session, run, version].append(dict(
            subject=subject, session=session, task=task, run=run, era=version,
            bids=str(path), payload=payload))
    selected = []
    for key, rows in sorted(groups.items()):
        # One echo-1 sidecar per participant/stratum; ambiguous duplicates stop us.
        if len({r["subject"] for r in rows}) != len(rows):
            raise ValueError("duplicate canonical sidecars in sampling stratum")
        n = min(count, len(rows))
        indices = [len(rows) // 2] if n == 1 else [
            round(i * (len(rows) - 1) / (n - 1)) for i in range(n)]
        selected.extend(rows[i] for i in indices)
    return selected, {"|".join(k): len(v) for k, v in sorted(groups.items())}


def values(ds, keyword):
    return {str(e.value) for e in ds.iterall() if e.keyword == keyword}


def matching_header(ds, row):
    payload = row["payload"]
    if str(getattr(ds, "SeriesNumber", "")) != str(payload.get("SeriesNumber", "")):
        return False
    if era(getattr(ds, "SoftwareVersions", "")) != row["era"]:
        return False
    if payload.get("SeriesDescription") and str(getattr(ds, "SeriesDescription", "")) != payload["SeriesDescription"]:
        return False
    for key in ("StudyInstanceUID", "SeriesInstanceUID"):
        if payload.get(key) and str(getattr(ds, key, "")) != payload[key]:
            return False
    kind = {str(x) for x in getattr(ds, "ImageType", [])}
    magnitude = "M" in kind or "MAGNITUDE" in values(ds, "ComplexImageComponent")
    if not magnitude or "SBREF" in str(getattr(ds, "SeriesDescription", "")).upper():
        return False
    times = values(ds, "EchoTime") | values(ds, "EffectiveEchoTime")
    expected = float(payload["EchoTime"]) * 1000
    return bool(times) and all(abs(float(v) - expected) < 0.01 for v in times)


def source_header(source, row, max_headers, reader):
    subject, session = row["subject"], row["session"]
    base = f"Smith-SRA-{subject}" + (f"-{int(session)}" if session != "01" else "")
    folders = [p for p in source.iterdir() if p.is_dir() and
               (p.name == base or (session != "01" and p.name.startswith(base + "-")))]
    series = str(row["payload"].get("SeriesNumber", ""))
    if not re.fullmatch(r"\d+", series):
        raise ValueError("missing numeric BIDS series number")
    candidates, scan_dirs, checked = [], [], 0
    for folder in sorted(folders):
        for scans in sorted(folder.rglob("scans")):
            scan_dirs.extend(p for p in scans.iterdir() if p.is_dir() and
                             re.match(rf"{re.escape(series)}(?:-|_|$)", p.name))
    for scan in sorted(set(scan_dirs)):
        paths = sorted(p for p in scan.rglob("*") if p.is_file() and
                       p.suffix.lower() in {".dcm", ".ima"})
        for path in paths[:max_headers]:
            ds = reader(path)
            checked += 1
            if matching_header(ds, row):
                identity = (str(getattr(ds, "StudyInstanceUID", "")),
                            str(getattr(ds, "SeriesInstanceUID", "")))
                if not all(identity):
                    raise ValueError("source identity missing")
                candidates.append((identity, path, ds))
                break
    if len({item[0] for item in candidates}) != 1:
        raise ValueError("no unique source series within bounded header search")
    _, path, ds = candidates[0]
    link = "series_uid_match" if row["payload"].get("SeriesInstanceUID") else "metadata_candidate_only"
    return path, ds, dict(link=link, headers_checked=checked,
                          candidate_directories=len(scan_dirs), copies=len(candidates))


def extract_fields(ds, csa_reader, asc_parser):
    fields, protocols, notes = defaultdict(set), [], []

    def add(key, value):
        fields[key].add(json.dumps(value, sort_keys=True, default=str))

    def inspect_text(value, origin):
        text = value.decode("latin1") if isinstance(value, bytes) else str(value)
        # Keep the block intact for NiBabel's structured parser; never execute it.
        blocks = re.findall(r"### ASCCONV BEGIN[^\n]*\n.*?### ASCCONV END[^\n]*", text, re.S)
        for block in blocks:
            try:
                parsed, attributes, declarations = parse_protocol(block, asc_parser)
                protocols.append(dict(origin=origin, attributes=attributes, values=parsed,
                                      array_declarations=declarations))
                for key, val in flatten(parsed, "ASCCONV"):
                    add(key, val)
            except Exception as exc:
                notes.append(dict(origin=origin, status="ascconv_decode_error", error=type(exc).__name__))

    opaque = []
    for element in ds.iterall():
        if element.VR == "SQ":
            continue
        if element.keyword in STANDARD:
            add("DICOM." + element.keyword, str(element.value))
        if element.tag.is_private:
            key = f"PRIVATE.{getattr(element, 'private_creator', '')}.{element.tag}.{element.name}"
            if isinstance(element.value, bytes):
                opaque.append(dict(field=key, bytes=len(element.value), sha256=hashlib.sha256(element.value).hexdigest()))
            else:
                add(key, str(element.value))
            inspect_text(element.value, key)
    for kind in ("image", "series"):
        try:
            header = csa_reader(ds, kind)
            notes.append(dict(origin=kind, status="csa_present" if header else "csa_absent"))
            if header:
                for name, entry in header["tags"].items():
                    for item in entry.get("items", []):
                        if name not in {"MrPhoenixProtocol", "MrProtocol"}:
                            add("CSA." + name, item)
                        inspect_text(item, "CSA." + name)
        except Exception as exc:
            notes.append(dict(origin=kind, status="csa_decode_error", error=type(exc).__name__))
    return {k: sorted(v) for k, v in fields.items()}, dict(
        protocols=protocols, decoder_notes=notes, opaque_private_elements=opaque,
        ascconv_blocks=len(protocols))


def compare(samples, eras):
    groups = defaultdict(list)
    for sample in samples:
        if sample["status"] == "collected":
            groups[sample["task"], sample["session"], sample["run"]].append(sample)
    result = []
    for (task, session, run), rows in sorted(groups.items()):
        for key in sorted({k for r in rows for k in r["fields"]}):
            entry = dict(task=task, session=session, run=run, field=key,
                         reconstruction_related=bool(INTEREST.search(key)))
            complete, sets = True, []
            for version in eras:
                subset = [r for r in rows if r["era"] == version]
                present = [r for r in subset if key in r["fields"]]
                unique = sorted({v for r in present for v in r["fields"][key]})
                entry[version + "_coverage"] = f"{len(present)}/{len(subset)}"
                entry[version + "_values"] = json.dumps(unique)
                complete &= bool(subset) and len(present) == len(subset)
                sets.append(unique)
            entry["status"] = "incomplete_evidence" if not complete else (
                "same_observed_value_sets" if all(s == sets[0] for s in sets[1:]) else "different_observed_value_sets")
            result.append(entry)
    return result


def write_table(path, rows, columns):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def report(samples, comparison):
    lines = ["# Read-only DICOM reconstruction inspection", "",
             "Evidence collection only; no source-validity, causal or exclusion decision.",
             "Header values and exact source linkage remain in ignored work/.", "",
             "task | session | run | era | selected | collected | exact series UID | ASCCONV available",
             "---|---|---|---|---|---|---|---"]
    groups = defaultdict(list)
    for row in samples:
        groups[row["task"], row["session"], row["run"], row["era"]].append(row)
    for key, rows in sorted(groups.items()):
        ok = [r for r in rows if r["status"] == "collected"]
        counts = [len(rows), len(ok), sum(r["mapping"]["link"] == "series_uid_match" for r in ok),
                  sum(r["extraction"]["ascconv_blocks"] > 0 for r in ok)]
        lines.append(" | ".join([*key, *map(str, counts)]))
    lines += ["", "Field-comparison counts (descriptive, not independent observations):"]
    lines += [f"- {k}: {v}" for k, v in sorted(Counter(r["status"] for r in comparison).items())]
    lines += ["", "Absent/undecodable private fields are unknown, not equal or disabled.",
              "Metadata-only source candidates are not exact conversion-provenance links.",
              "This samples echo 1 and selected instances, not all frames/echoes/participants.",
              "Header-only collection does not establish image smoothness or reconstruction causality."]
    return "\n".join(lines) + "\n"


def run(args):
    project, private = args.project.resolve(), args.private_dir.resolve()
    work = (project / "work").resolve()
    if not private.is_relative_to(work) or private == work or private.exists():
        raise ValueError("use a new directory inside ignored project work/")
    ignored = subprocess.run(["git", "-C", str(project), "check-ignore", "-q", str(private / "inventory-private.json")])
    if ignored.returncode != 0:
        raise ValueError("output directory is not Git ignored")
    if not args.source_root.is_dir() or not (project / "bids").is_dir():
        raise ValueError("source or BIDS root unavailable")
    import pydicom
    import nibabel
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from nibabel.nicom import csareader, ascconv
    os.umask(0o000)
    private.mkdir(parents=True)
    samples, population = select_samples(project / "bids", args.sessions, args.eras, args.per_stratum)
    if not samples:
        raise ValueError("no eligible live BIDS sidecars")
    dump(private / "selection-private.json", dict(population=population, samples=samples))
    output = []
    for index, row in enumerate(samples, 1):
        record = {k: v for k, v in row.items() if k != "payload"}
        dest = private / f"sample-{index:03d}"
        dest.mkdir()
        try:
            if json.loads(Path(row["bids"]).read_text()) != row["payload"]:
                raise ValueError("BIDS sidecar changed since sample selection")
            # Warning messages can include identifiers; preserve only their count.
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                path, ds, mapping = source_header(args.source_root, row, args.max_headers,
                    lambda p: pydicom.dcmread(p, stop_before_pixels=True))
                before = path.stat()
                fields, extraction = extract_fields(ds, csareader.get_csa_header, ascconv.parse_ascconv)
                with gzip.open(dest / "header-private.json.gz", "wt") as stream:
                    json.dump(ds.to_json_dict(), stream)
                for key, value in row["payload"].items():
                    fields["BIDS." + key] = [json.dumps(value, sort_keys=True)]
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("source changed during inspection")
            if json.loads(Path(row["bids"]).read_text()) != row["payload"]:
                raise ValueError("BIDS sidecar changed during inspection")
            dump(dest / "decoded-private.json", extraction)
            dump(dest / "bids-private.json", row["payload"])
            record.update(status="collected", source=str(path), mapping=mapping,
                source_size=before.st_size, source_mtime_ns=before.st_mtime_ns,
                bids_sha256=sha(Path(row["bids"])), fields=fields,
                warnings=len(caught), extraction=extraction)
        except Exception as exc:
            record.update(status="error", error_type=type(exc).__name__)
            (dest / "error-private.txt").write_text(traceback.format_exc())
        output.append(record)
        print(f"Sample {index}/{len(samples)}: {record['status']}", flush=True)
    comparison = compare(output, args.eras)
    columns = ["task", "session", "run", "field", "reconstruction_related", "status"]
    columns += [e + suffix for e in args.eras for suffix in ("_coverage", "_values")]
    write_table(private / "comparison-private.tsv", comparison, columns)
    write_table(private / "reconstruction-private.tsv", [r for r in comparison if r["reconstruction_related"]], columns)
    dump(private / "inventory-private.json", dict(population=population, samples=output))
    summary = report(output, comparison)
    (private / "summary.md").write_text(summary)
    dump(private / "provenance.json", dict(script_sha256=sha(Path(__file__)),
        pydicom_version=pydicom.__version__, nibabel_version=nibabel.__version__, arguments=vars(args),
        outputs={str(p.relative_to(private)): sha(p) for p in private.rglob("*") if p.is_file()}))
    print(summary)
    failures = sum(r["status"] != "collected" for r in output)
    print("CHECK FAILED: header collection incomplete." if failures else
          "CHECK PASSED: selected headers collected; decoder/linkage gaps remain explicit.")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra"))
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--sessions", nargs="+", choices=("01", "02"), default=["01", "02"])
    parser.add_argument("--eras", nargs="+", choices=ERAS, default=list(ERAS))
    parser.add_argument("--per-stratum", type=int, default=3)
    parser.add_argument("--max-headers", type=int, default=32)
    args = parser.parse_args()
    if args.per_stratum < 1 or args.max_headers < 1 or len(set(args.eras)) < 2:
        parser.error("positive sample/header limits and at least two distinct eras required")
    try:
        return run(args)
    except Exception as exc:
        print(f"ERROR: inspection stopped ({type(exc).__name__}); check paths/dependencies privately.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
