#!/usr/bin/env python3
"""Small keyboard-first overlay for CSES Kit.

This stays thin: it reads roadmap data and local config, then calls the existing
library functions for fetch/open/run/status instead of re-implementing the CLI.
"""
from __future__ import annotations

import curses
import os
import re
import sys

from cses_lib import (
    collect_status,
    fetch_problem,
    load_dotenv,
    open_in_editor,
    repo_root,
    slugify_category,
    slugify_problem,
)
from roadmap import load_roadmap


def default_roadmap_path() -> str:
    return os.path.join(repo_root(), "roadmaps", "roadmap.txt")


def configured_repo_path() -> str:
    load_dotenv()
    value = os.environ.get("CSES_PROBLEMS_DIR", "").strip()
    return value or os.path.join(repo_root(), "problems")


def configured_editor() -> str:
    load_dotenv()
    return os.environ.get("CSES_EDITOR", "code").strip() or "code"


def configured_roadmap_path() -> str:
    load_dotenv()
    value = os.environ.get("CSES_ROADMAP", "").strip()
    return value or default_roadmap_path()


class RoadmapEntry:
    def __init__(self, item: dict[str, object], repo_path: str):
        self.item = item
        self.repo_path = repo_path
        self.id = int(item.get("id", 0))
        self.name = str(item.get("name") or "Unknown")
        self.category = str(item.get("category") or "misc")
        self.repo_category = str(item.get("category_slug") or slugify_category(self.category))
        self.url = str(item.get("link") or item.get("url") or "")
        self.slug = slugify_problem(self.name)
        self.problem_dir = os.path.join(self.repo_path, self.repo_category, self.slug)
        self.downloaded = os.path.isdir(self.problem_dir)
        self.solved = False
        self.failed = False


class TuiState:
    def __init__(self, repo_path: str | None = None, roadmap_path: str | None = None):
        self.repo_path = repo_path or configured_repo_path()
        self.roadmap_path = roadmap_path or configured_roadmap_path()
        self.entries: list[RoadmapEntry] = []
        self.display_rows: list[tuple[str, str | None, RoadmapEntry | None]] = []
        self.selected_index = 0
        self.scroll_offset = 0
        self.refresh()

    def refresh(self):
        self.entries = self._load_entries()
        self._sync_status()
        self.display_rows = self._build_display_rows()
        if not self.display_rows:
            self.selected_index = 0
            self.scroll_offset = 0
            return
        self.selected_index = max(0, min(self.selected_index, len(self.display_rows) - 1))
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        max_visible = 20
        if self.selected_index >= self.scroll_offset + max_visible:
            self.scroll_offset = self.selected_index - max_visible + 1

    def _build_display_rows(self) -> list[tuple[str, str | None, RoadmapEntry | None]]:
        grouped: dict[str, list[RoadmapEntry]] = {}
        for entry in self.entries:
            grouped.setdefault(entry.category, []).append(entry)
        rows: list[tuple[str, str | None, RoadmapEntry | None]] = []
        for category in grouped:
            rows.append(("header", category, None))
            for entry in grouped[category]:
                rows.append(("item", category, entry))
        return rows

    def _load_entries(self) -> list[RoadmapEntry]:
        try:
            items = load_roadmap(self.roadmap_path)
            if not items:
                fallback = default_roadmap_path()
                if os.path.exists(fallback):
                    items = load_roadmap(fallback)
        except OSError:
            return []
        entries = []
        for item in items:
            entries.append(RoadmapEntry(item, self.repo_path))
        return entries

    def _sync_status(self):
        status_data = collect_status(base_dir=self.repo_path)
        solved = set()
        failed = set()
        for category, data in status_data.items():
            for slug in data["solved"]:
                solved.add((category, slug))
            for slug in data["unsolved"]:
                path = os.path.join(self.repo_path, category, slug)
                stmt = os.path.join(path, "statement.md")
                if os.path.isfile(stmt):
                    try:
                        text = open(stmt, "r", encoding="utf-8", errors="replace").read()
                    except OSError:
                        text = ""
                    if re.search(r"\*\*Verdict:\*\*.*(?:WA|TLE|MLE|RE|RTE|CE|FAILED|WRONG|REJECTED)", text, flags=re.I):
                        failed.add((category, slug))
        for entry in self.entries:
            entry.solved = (entry.repo_category, entry.slug) in solved or (entry.repo_category, os.path.basename(entry.problem_dir)) in solved
            entry.failed = (entry.repo_category, entry.slug) in failed or (entry.repo_category, os.path.basename(entry.problem_dir)) in failed
            entry.downloaded = os.path.isdir(entry.problem_dir)

    def selected(self):
        if not self.display_rows:
            return None
        kind, _, item = self.display_rows[self.selected_index]
        if kind != "item":
            return None
        return item

    def move_selection(self, delta: int):
        if not self.display_rows:
            return
        target = self.selected_index + delta
        while 0 <= target < len(self.display_rows):
            kind, _, _ = self.display_rows[target]
            if kind == "item":
                self.selected_index = target
                break
            target += delta
        if target < 0 or target >= len(self.display_rows):
            self.selected_index = max(0, min(self.selected_index, len(self.display_rows) - 1))


class TuiApp:
    def __init__(self, stdscr, repo_path: str | None = None, roadmap_path: str | None = None):
        self.stdscr = stdscr
        self.state = TuiState(repo_path=repo_path, roadmap_path=roadmap_path)

    def run(self):
        self.stdscr.nodelay(False)
        self.stdscr.keypad(True)
        curses.curs_set(0)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_RED, -1)
            curses.init_pair(4, curses.COLOR_YELLOW, -1)
            curses.init_pair(5, curses.COLOR_WHITE, -1)
        while True:
            self.draw()
            key = self.stdscr.getch()
            if key in (ord("q"), ord("Q")):
                return
            if key in (curses.KEY_UP, ord("k")):
                self.state.move_selection(-1)
            elif key in (curses.KEY_DOWN, ord("j")):
                self.state.move_selection(1)
            elif key in (10, 13, curses.KEY_ENTER):
                self._open_selected()
            elif key in (ord("d"), ord("D")):
                self._download_selected()
            elif key in (ord("r"), ord("R")):
                self.state.refresh()
            self._ensure_visible()

    def _ensure_visible(self):
        if not self.state.display_rows:
            return
        if self.state.selected_index < self.state.scroll_offset:
            self.state.scroll_offset = self.state.selected_index
        max_visible = max(4, self._visible_rows() - 3)
        if self.state.selected_index >= self.state.scroll_offset + max_visible:
            self.state.scroll_offset = self.state.selected_index - max_visible + 1

    def _visible_rows(self):
        h, _ = self.stdscr.getmaxyx()
        return max(4, h - 8)

    def _download_selected(self):
        item = self.state.selected()
        if not item:
            return
        os.makedirs(os.path.dirname(item.problem_dir), exist_ok=True)
        try:
            fetch_problem(item.url, item.problem_dir)
            item.downloaded = True
        except Exception:
            pass
        self.state.refresh()

    def _open_selected(self):
        item = self.state.selected()
        if not item:
            return
        if not item.downloaded:
            self._download_selected()
        if not item.downloaded:
            return
        default_candidates = [
            os.path.join(item.problem_dir, "sol.cpp"),
            os.path.join(item.problem_dir, "sol.py"),
            os.path.join(item.problem_dir, "sol.js"),
            os.path.join(item.problem_dir, "statement.md"),
        ]
        target = next((p for p in default_candidates if os.path.isfile(p)), item.problem_dir)
        open_in_editor(target)

    def draw(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        self.stdscr.addstr(0, 0, "CSES Kit"[:w-1])
        self.stdscr.addstr(1, 0, ("-" * max(1, min(w - 1, 40)))[:w-1])

        if not self.state.display_rows:
            self.stdscr.addstr(3, 0, "No roadmap problems loaded.")
            self.stdscr.addstr(h - 2, 0, "q Quit")
            self.stdscr.refresh()
            return

        row = 3
        visible_rows = self._visible_rows()
        end_index = min(len(self.state.display_rows), self.state.scroll_offset + visible_rows)
        for idx in range(self.state.scroll_offset, end_index):
            kind, category, item = self.state.display_rows[idx]
            if kind == "header":
                label = f"{category}"
                attr = curses.color_pair(1) | curses.A_BOLD
                self.stdscr.addstr(row, 0, label[:w-1], attr)
                row += 1
                continue

            if item is None:
                continue
            if item.solved:
                marker = "✓"
                color = curses.color_pair(2)
            elif item.failed:
                marker = "✗"
                color = curses.color_pair(3)
            elif item.downloaded:
                marker = "●"
                color = curses.color_pair(4)
            else:
                marker = "○"
                color = curses.color_pair(5)

            line = f"{marker} {item.name}"
            if idx == self.state.selected_index:
                self.stdscr.addstr(row, 0, line[:w-1], color | curses.A_REVERSE)
            else:
                self.stdscr.addstr(row, 0, line[:w-1], color)
            row += 1

        footer = "↑ ↓ Navigate   Enter Open   d Download   m Roadmap   q Quit"
        self.stdscr.addstr(max(3, h - 2), 0, footer[:w-1])

        item = self.state.selected()
        if item:
            selected = f"Selected: {item.name}"
            self.stdscr.addstr(max(3, h - 6), 0, selected[:w - 1])
            if item.solved:
                status_text = "Solved"
            elif item.failed:
                status_text = "Attempted and failed"
            elif item.downloaded:
                status_text = "Downloaded"
            else:
                status_text = "Not downloaded"
            self.stdscr.addstr(max(4, h - 5), 0, f"Status: {status_text}"[:w - 1])

        self.stdscr.refresh()


def run_tui(repo_path: str | None = None, roadmap_path: str | None = None) -> int:
    try:
        curses.wrapper(lambda stdscr: TuiApp(stdscr, repo_path=repo_path, roadmap_path=roadmap_path).run())
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: could not load roadmap: {exc}", file=sys.stderr)
        return 1
    return 0
