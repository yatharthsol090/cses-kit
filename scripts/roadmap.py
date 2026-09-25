#!/usr/bin/env python3
"""Roadmap import helpers for the CSES Kit TUI.

This is intentionally small and uses Python's standard json library only.
It consumes roadmap files from the local repo, preserves ordering, keeps
roadmap data separate from solving state, and supports both default and custom
CSES roadmaps.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable


def normalize_category_name(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return "misc"
    value = value.lower().replace("/", " ")
    value = "".join(ch if ch.isalnum() or ch in ("_", "-") else " " for ch in value)
    return "_".join(value.split())


def parse_roadmap_json(path: str) -> list[dict[str, object]]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list):
        return [dict(item) for item in data]
    if isinstance(data, dict):
        items = data.get("problems", [])
        if isinstance(items, list):
            return [dict(item) for item in items]
        if isinstance(items, dict):
            return [dict(item) for item in items.values() if isinstance(item, dict)]
        if data and all(isinstance(item, dict) for item in data.values()):
            return [dict(item) for item in data.values()]
    raise ValueError(f"unsupported roadmap JSON format: {path}")


def load_problem_index(path: str) -> dict[str, dict[str, object]]:
    """Load the canonical link-keyed metadata index."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("problems", list(data.values()))
    else:
        raise ValueError(f"problem index must contain records: {path}")
    return {
        str(item.get("link") or item.get("url")): dict(item)
        for item in records
        if isinstance(item, dict) and (item.get("link") or item.get("url"))
    }


def save_problem_index(path: str, index: dict[str, dict[str, object]] | list[dict[str, object]]) -> None:
    records = list(index.values()) if isinstance(index, dict) else index
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2)
        fh.write("\n")


def parse_roadmap_txt(path: str) -> list[dict[str, object]]:
    """Parse one ordered task id, URL, or slug per non-comment line."""
    items: list[dict[str, object]] = []
    record_pattern = re.compile(
        r"(\d+)\s+(https://cses\.fi/problemset/task/(\d+))\s+([a-z0-9]+(?:-[a-z0-9]+)*)/?$"
    )
    url_pattern = re.compile(r"https://cses\.fi/problemset/task/(\d+)/?$")
    slug_pattern = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*$")
    with open(path, "r", encoding="utf-8") as fh:
        for line_number, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            item: dict[str, object] = {"category": "roadmap"}
            if (match := record_pattern.fullmatch(line)):
                item_id, url, url_id, slug = match.groups()
                if item_id != url_id:
                    raise ValueError(f"{path}:{line_number}: unknown roadmap line: {line}")
                item.update({
                    "id": item_id,
                    "url": url,
                    "link": url,
                    "slug": slug,
                    "name": slug.replace("-", " ").title(),
                })
            elif line.isdigit():
                item_id = line
                item.update({
                    "id": item_id,
                    "url": f"https://cses.fi/problemset/task/{item_id}",
                    "link": f"https://cses.fi/problemset/task/{item_id}",
                    "slug": item_id,
                    "name": item_id,
                })
            elif (match := url_pattern.fullmatch(line)):
                item_id = match.group(1)
                item.update({
                    "id": item_id,
                    "url": line.rstrip("/"),
                    "link": line.rstrip("/"),
                    "slug": item_id,
                    "name": item_id,
                })
            elif slug_pattern.fullmatch(line):
                item.update({
                    "slug": line,
                    "name": line.replace("-", " ").title(),
                })
            else:
                raise ValueError(f"{path}:{line_number}: unknown roadmap line: {line}")
            items.append(item)
    if not items:
        raise ValueError(f"{path}: roadmap contains no problem records")
    return items


def load_roadmap(path: str) -> list[dict[str, object]]:
    suffix = os.path.splitext(path)[1].lower()
    if suffix == ".json":
        return parse_roadmap_json(path)
    if suffix in {".txt", ".list"}:
        return parse_roadmap_txt(path)
    raise ValueError(f"unsupported roadmap format: {path}")


def build_default_roadmap(source_path: str) -> list[dict[str, object]]:
    """Parse the upstream Problems.txt and return a normalized default roadmap."""
    text = Path(source_path).read_text(encoding="utf-8")
    pattern = re.compile(r'(?ms)^(.+?)\n\[(.*?)\]\s*(?=\n[A-Za-z][^\n]*\n\[|\Z)')
    result: list[dict[str, object]] = []
    for match in pattern.finditer(text):
        category = match.group(1).strip()
        block = match.group(2).strip()
        if not block:
            continue
        try:
            payload = json.loads("[" + block + "]")
        except json.JSONDecodeError:
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            url = item.get("a_link") or item.get("_container_link") or item.get("url") or ""
            pid = item.get("id")
            if pid is None:
                m = re.search(r"/task/(\d+)", url)
                pid = int(m.group(1)) if m else 0
            result.append({
                "id": int(pid),
                "name": item.get("a") or item.get("name") or "Unknown",
                "category": category,
                "category_slug": normalize_category_name(category),
                "url": url,
            })

    # Problems.txt has one older mixed section: six interactive entries are
    # plain name/link pairs before the Bitwise Operations JSON block.
    mixed = re.search(
        r"(?ms)^Interactive Problems\n(.*?)^Bitwise Operations\n\[(.*?)\]\s*\n^Construction Problems$",
        text,
    )
    if mixed:
        lines = [line.strip() for line in mixed.group(1).splitlines() if line.strip()]
        for name, url in zip(lines[0::2], lines[1::2]):
            match = re.fullmatch(r"https://cses\.fi/problemset/task/(\d+)", url)
            if not match:
                continue
            result.append({
                "id": int(match.group(1)),
                "name": name,
                "category": "Interactive Problems",
                "category_slug": normalize_category_name("Interactive Problems"),
                "url": url,
            })
        try:
            payload = json.loads("[" + mixed.group(2).strip() + "]")
        except json.JSONDecodeError:
            payload = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            url = item.get("a_link") or item.get("_container_link") or ""
            match = re.search(r"/task/(\d+)", url)
            if not match:
                continue
            result.append({
                "id": int(match.group(1)),
                "name": item.get("a") or item.get("name") or "Unknown",
                "category": "Bitwise Operations",
                "category_slug": normalize_category_name("Bitwise Operations"),
                "url": url,
            })

    sliding = re.search(
        r"(?ms)^Sliding Window Problems\n\[(.*?)\]\s*\n^Interactive Problems$",
        text,
    )
    if sliding:
        try:
            payload = json.loads("[" + sliding.group(1).strip() + "]")
        except json.JSONDecodeError:
            payload = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            url = item.get("a_link") or item.get("_container_link") or ""
            match = re.search(r"/task/(\d+)", url)
            if not match:
                continue
            result.append({
                "id": int(match.group(1)),
                "name": item.get("a") or item.get("name") or "Unknown",
                "category": "Sliding Window Problems",
                "category_slug": normalize_category_name("Sliding Window Problems"),
                "url": url,
            })
    return result


def build_default_roadmap_from_tasks(
    tasks: Iterable[dict[str, object]],
    repo_root: str | None = None,
) -> list[dict[str, object]]:
    """Return a clean roadmap entry for each CSES task including local path/status."""
    root = repo_root or os.getcwd()
    out: list[dict[str, object]] = []
    for task in tasks:
        category = str(task.get("section") or task.get("category") or "misc")
        category_slug = str(
            task.get("category_slug") or task.get("category") or normalize_category_name(category)
        )
        name = str(task.get("title") or task.get("name") or "Unknown")
        task_id = str(task.get("id") or task.get("tid") or "0")
        url = str(task.get("url") or f"https://cses.fi/problemset/task/{task_id}")
        local_dir = os.path.join(root, "problems", category_slug, slugify_text(name))
        downloaded = os.path.isdir(local_dir)
        out.append({
            "id": int(task_id) if str(task_id).isdigit() else 0,
            "name": name,
            "category": category,
            "category_slug": category_slug,
            "url": url,
            "downloaded": downloaded,
            "local_path": os.path.join("problems", category_slug, slugify_text(name)),
        })
    return out


def build_problem_index_from_tasks(
    tasks: Iterable[dict[str, object]],
    repo_root: str | None = None,
) -> list[dict[str, object]]:
    """Build immutable roadmap records from parsed CSES tasks."""
    records = build_default_roadmap_from_tasks(tasks, repo_root=repo_root)
    return [
        {
            "id": record["id"],
            "name": record["name"],
            "category": record["category"],
            "link": record["url"],
        }
        for record in records
        if record.get("id")
    ]


def slugify_text(value: str) -> str:
    s = (value or "problem").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "problem"
