#!/usr/bin/env python3
"""Validate repository metadata that can be checked without production data."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


SCRIPT_RE = re.compile(r"`([^`]+\.(?:sh|py|m|json|txt))`|(?:bash|python(?:3)?)\s+([A-Za-z0-9_./+-]+\.(?:sh|py))")


def git_ls_files(repo: Path, pattern: str | None = None) -> list[str]:
    cmd = ["git", "-C", str(repo), "ls-files"]
    if pattern:
        cmd.append(pattern)
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return [line for line in result.stdout.splitlines() if line]


def validate_json(repo: Path) -> list[str]:
    errors: list[str] = []
    for rel in git_ls_files(repo, "*.json"):
        path = repo / rel
        try:
            json.loads(path.read_text())
        except Exception as exc:  # noqa: BLE001 - include parser message in validation output.
            errors.append(f"{rel}: {exc}")
    return errors


def validate_readme_paths(repo: Path) -> list[str]:
    errors: list[str] = []
    for readme in [repo / "README.md", repo / "code" / "README.md"]:
        if not readme.exists():
            errors.append(f"missing {readme.relative_to(repo)}")
            continue
        for match in SCRIPT_RE.finditer(readme.read_text()):
            token = next(group for group in match.groups() if group)
            if token.startswith("/") or "*" in token:
                continue
            rel = token.removeprefix("./")
            candidates = [repo / rel, repo / "code" / rel]
            if not any(candidate.exists() for candidate in candidates):
                errors.append(f"{readme.relative_to(repo)} references missing path: {token}")
    return errors


def validate_clean_status(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--short"],
        check=True,
        text=True,
        capture_output=True,
    )
    ignored = [line for line in result.stdout.splitlines() if line.startswith("?? .pytest_cache/")]
    return [f"unexpected generated status line: {line}" for line in ignored]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    repo = args.repo_root.resolve()

    errors = validate_json(repo)
    errors.extend(validate_readme_paths(repo))
    errors.extend(validate_clean_status(repo))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Repository metadata validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
