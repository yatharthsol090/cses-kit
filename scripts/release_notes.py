#!/usr/bin/env python3
"""Pull a CHANGELOG.md section for a git tag and check it against VERSION.

Usage:
    python3 scripts/release_notes.py v0.1.0
    python3 scripts/release_notes.py --check v0.1.0
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def tag_to_version(tag: str) -> str:
    s = tag.strip()
    if s.startswith("v") or s.startswith("V"):
        s = s[1:]
    if not re.fullmatch(r"\d+\.\d+\.\d+", s):
        raise ValueError(f"not a vMAJOR.MINOR.PATCH tag: {tag!r}")
    return s


def read_version_file(root: str) -> str:
    path = os.path.join(root, "VERSION")
    try:
        with open(path, encoding="utf-8") as f:
            ver = f.read().strip()
    except OSError as e:
        raise ValueError(f"could not read {path}: {e}") from e
    if not re.fullmatch(r"\d+\.\d+\.\d+", ver):
        raise ValueError(f"VERSION is not MAJOR.MINOR.PATCH: {ver!r}")
    return ver


def changelog_section(text: str, version: str) -> str:
    heading = re.compile(
        rf"^## \[{re.escape(version)}\](?:\s+-.*)?\s*$", flags=re.M
    )
    m = heading.search(text)
    if not m:
        raise ValueError(f"no CHANGELOG.md heading for [{version}]")
    rest = text[m.end() :]
    nxt = re.search(r"^## \[", rest, flags=re.M)
    body = rest[: nxt.start()] if nxt else rest
    kept = [
        line
        for line in body.splitlines()
        if not re.fullmatch(r"\[[^\]]+\]:\s+\S+", line.strip())
    ]
    body = "\n".join(kept)
    return (m.group(0).strip() + "\n" + body).strip() + "\n"


def notes_for_tag(tag: str, root: str = ROOT) -> str:
    version = tag_to_version(tag)
    file_ver = read_version_file(root)
    if file_ver != version:
        raise ValueError(
            f"tag {tag} is version {version}, but VERSION is {file_ver}"
        )
    path = os.path.join(root, "CHANGELOG.md")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise ValueError(f"could not read {path}: {e}") from e
    return changelog_section(text, version)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tag", help="git tag, e.g. v0.1.0")
    p.add_argument(
        "--root",
        default=ROOT,
        help="repo root (default: parent of scripts/)",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="verify VERSION and CHANGELOG, print nothing on success",
    )
    args = p.parse_args()
    try:
        notes = notes_for_tag(args.tag, root=args.root)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not args.check:
        sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
