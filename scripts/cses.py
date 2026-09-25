#!/usr/bin/env python3
"""CSES local workflow: sync the problem set, log in, and submit.

Usage:
    cses sync [--category CAT] [--delay SEC] [--dry-run]
    cses login
    cses whoami
    cses run [slug|path] [-i]
    cses submit [slug|path]
    cses next [slug|path]
    cses fetch <cses-task-url> <problem-dir>
    cses new <category> <slug> [url]
    cses status [--category CAT] [-u|--unsolved] [--json]
    cses install
    cses celebrate
    cses version
"""
from __future__ import annotations

import argparse
import getpass
import math
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cses_lib import (
    CurlError,
    celebrate as do_celebrate,
    collect_status,
    existing_problems,
    ensure_sol_cpp,
    env_credentials,
    fetch,
    fetch_problem,
    find_problem,
    format_status_report,
    LIST_URL,
    load_dotenv,
    login as do_login,
    next_unsolved,
    offer_next,
    package_version,
    parse_problem_list,
    problem_dir_for,
    repo_root,
    slugify_category,
    submit_solution,
    whoami,
)
from cses_tui import run_tui
from roadmap import load_roadmap
from setup_flow import cmd_setup


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0 or not math.isfinite(number):
        raise argparse.ArgumentTypeError("must be a positive number")
    return number


def cmd_fetch(args: argparse.Namespace) -> int:
    try:
        title, n = fetch_problem(args.url, args.dir)
    except Exception as e:  # noqa: BLE001
        print(f"error: could not fetch {args.url}: {e}", file=sys.stderr)
        return 1
    extra = f"{n} sample test(s)" if n else "no sample tests found"
    print(f"fetched: {title}  ({extra})")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    try:
        if getattr(args, "list_path", None):
            tasks = load_roadmap(args.list_path)
        else:
            print("listing CSES problem set …", flush=True)
            page = fetch(LIST_URL)
            tasks = parse_problem_list(page)
    except Exception as e:  # noqa: BLE001
        print(f"error: could not load problem list: {e}", file=sys.stderr)
        return 1
    if not tasks:
        print("error: parsed 0 problems from the list page", file=sys.stderr)
        return 1

    if args.category:
        want = args.category.replace("-", "_").lower()
        tasks = [
            t
            for t in tasks
            if t["category"] == want or slugify_category(t["section"]) == want
        ]
        if not tasks:
            print(f"error: no problems in category {args.category!r}", file=sys.stderr)
            return 1

    by_id = existing_problems()
    created = refreshed = failed = 0
    total = len(tasks)
    print(f"{total} problem(s) to sync", flush=True)

    for i, task in enumerate(tasks, start=1):
        url = task.get("url")
        if not isinstance(url, str) or not url:
            failed += 1
            slug = str(task.get("slug", "unknown"))
            print(
                f"[{i}/{total}] ERROR  cannot sync {slug!r}: roadmap entry has no task URL",
                file=sys.stderr,
                flush=True,
            )
            continue
        dest = problem_dir_for(task, by_id)
        task_id = str(task.get("id", ""))
        if task_id:
            by_id.setdefault(task_id, dest)
        rel = os.path.relpath(dest, repo_root())
        existed = os.path.isdir(dest) and os.path.isfile(os.path.join(dest, "statement.md"))
        prefix = f"[{i}/{total}] {rel}"

        if args.dry_run:
            action = "refresh" if existed else "create"
            print(f"{prefix}  ({action})  {task['url']}")
            continue

        try:
            os.makedirs(os.path.join(dest, "tests"), exist_ok=True)
            ensure_sol_cpp(dest)
            title, n = fetch_problem(url, dest)
            if task_id:
                by_id[task_id] = dest
            kind = "refresh" if existed else "create"
            if existed:
                refreshed += 1
            else:
                created += 1
            tests = f"{n} sample(s)" if n else "no samples"
            print(f"{prefix}  {kind}  {title}  ({tests})", flush=True)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"{prefix}  ERROR  {e}", file=sys.stderr, flush=True)

        if i < total and args.delay > 0:
            time.sleep(args.delay)

    if args.dry_run:
        return 1 if failed else 0
    print()
    print(f"created {created}, refreshed {refreshed}, failed {failed}")
    return 1 if failed else 0


def cmd_login(_args: argparse.Namespace) -> int:
    nick, password = env_credentials()
    if not nick:
        nick = input("CSES username: ").strip()
    if not password:
        password = getpass.getpass("CSES password: ")
    if not nick or not password:
        print("error: set CSES_NICK and CSES_PASS in .env, or type them at the prompt", file=sys.stderr)
        return 2
    try:
        name = do_login(nick, password)
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"logged in as {name}")
    print("session stored in .cses/cookies.txt  (gitignored)")
    return 0


def cmd_whoami(_args: argparse.Namespace) -> int:
    name = whoami()
    if not name:
        print("not logged in — set CSES_NICK and CSES_PASS in .env, or run: cses login")
        return 1
    print(name)
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    try:
        path, source = find_problem(args.target)
        return submit_solution(
            path, source=source, lang=args.lang, option=args.option
        )
    except CurlError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def cmd_next(args: argparse.Namespace) -> int:
    prob_dir = None
    if args.target:
        try:
            prob_dir, _ = find_problem(args.target)
        except CurlError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    else:
        try:
            prob_dir, _ = find_problem(None)
        except CurlError:
            prob_dir = None

    rel_dir = next_unsolved(prob_dir)
    if not rel_dir:
        if not existing_problems():
            print("no local unsolved problems — run cses sync")
        else:
            print("no unsolved problems found")
        return 0

    offer_next(rel_dir)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if getattr(args, "list_path", None):
        return cmd_run_list(args)
    try:
        path, source = find_problem(args.target)
    except CurlError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    cmd = [os.path.join(repo_root(), "scripts", "run.sh"), source or path]
    if args.interactive:
        cmd.append("-i")
    if args.timeout is not None:
        cmd.extend(("--timeout", str(args.timeout)))
    return subprocess.call(cmd)


def cmd_run_list(args: argparse.Namespace) -> int:
    try:
        entries = load_roadmap(args.list_path)
    except Exception as e:  # noqa: BLE001
        print(f"error: could not load problem list: {e}", file=sys.stderr)
        return 1
    by_id = existing_problems()
    result = 0
    for entry in entries:
        path = by_id.get(str(entry.get("id", "")))
        if not path:
            path = os.path.join(repo_root(), "problems", "roadmap", str(entry["slug"]))
        run_args = argparse.Namespace(
            target=path,
            interactive=args.interactive,
            timeout=args.timeout,
        )
        result = max(result, cmd_run(run_args))
    return result


def cmd_new(args: argparse.Namespace) -> int:
    dest = os.path.join(repo_root(), "problems", args.category, args.slug)
    if os.path.exists(dest):
        print(f"error: {dest} already exists", file=sys.stderr)
        return 2
    os.makedirs(os.path.join(dest, "tests"), exist_ok=True)
    ensure_sol_cpp(dest)
    if args.url:
        try:
            title, n = fetch_problem(args.url, dest)
        except Exception as e:  # noqa: BLE001
            print(f"warning: fetch failed ({e}) — blank statement", file=sys.stderr)
        else:
            extra = f"{n} sample(s)" if n else "no samples"
            print(f"created {dest}  {title}  ({extra})")
            return 0
    stmt = os.path.join(dest, "statement.md")
    if not os.path.isfile(stmt):
        with open(stmt, "w", encoding="utf-8") as f:
            f.write(f"# {args.slug}\n\n**Link:**\n")
        for name in ("1.in", "1.out"):
            open(os.path.join(dest, "tests", name), "a").close()
    print(f"created {dest}")
    return 0


def cmd_install(_args: argparse.Namespace) -> int:
    dest_dir = os.path.expanduser("~/.local/bin")
    dest = os.path.join(dest_dir, "cses")
    src = os.path.join(repo_root(), "cses")
    if not os.path.isfile(src):
        print(f"error: missing {src}", file=sys.stderr)
        return 1
    os.makedirs(dest_dir, mode=0o755, exist_ok=True)
    try:
        if os.path.islink(dest) or os.path.isfile(dest):
            os.remove(dest)
        os.symlink(src, dest)
    except OSError as e:
        print(f"error: could not install {dest}: {e}", file=sys.stderr)
        return 1
    print(f"installed {dest} -> {src}")
    print("this terminal:  export PATH=\"$HOME/.local/bin:$PATH\"")
    print("then:           cses run trailing-zeroes/sol.py")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    if getattr(args, "list_path", None):
        try:
            entries = load_roadmap(args.list_path)
        except Exception as e:  # noqa: BLE001
            print(f"error: could not load problem list: {e}", file=sys.stderr)
            return 1
        by_id = existing_problems()
        solved: list[str] = []
        unsolved: list[str] = []
        for entry in entries:
            path = by_id.get(str(entry.get("id", ""))) or os.path.join(
                repo_root(), "problems", "roadmap", str(entry["slug"])
            )
            stmt = os.path.join(path, "statement.md")
            try:
                text = open(stmt, encoding="utf-8", errors="replace").read()
            except OSError:
                text = ""
            target = solved if "**Verdict:**" in text and re.search(r"\bACCEPTED\b", text, re.I) else unsolved
            target.append(str(entry["slug"]))
        stats = {"roadmap": {"solved": solved, "unsolved": unsolved}}
    else:
        stats = collect_status(category=args.category)
    if args.json:
        import json

        payload = {
            "categories": stats,
            "total_solved": sum(len(d["solved"]) for d in stats.values()),
            "total_problems": sum(
                len(d["solved"]) + len(d["unsolved"]) for d in stats.values()
            ),
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(format_status_report(stats, show_unsolved=args.unsolved))
    return 0


def cmd_celebrate(args: argparse.Namespace) -> int:
    do_celebrate(args.title, args.score)
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"cses-kit {package_version()}")
    return 0


def cmd_tui(_args: argparse.Namespace) -> int:
    return run_tui(repo_path=_args.repo_path, roadmap_path=_args.roadmap)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cses",
        description="Sync CSES problems locally, log in, run samples, and submit.",
    )
    p.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"cses-kit {package_version()}",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("status", help="show solved vs remaining problems per category")
    st.add_argument(
        "--category",
        "-c",
        default=None,
        help="only this category (e.g. introductory)",
    )
    st.add_argument(
        "-u",
        "--unsolved",
        action="store_true",
        help="list unsolved problem slugs under each category",
    )
    st.add_argument(
        "--json",
        action="store_true",
        help="output status in JSON format",
    )
    st.add_argument("--list", dest="list_path", metavar="PATH", help="ordered roadmap.txt list")
    st.set_defaults(func=cmd_status)

    f = sub.add_parser("fetch", help="fetch one problem's statement + sample tests")
    f.add_argument("url")
    f.add_argument("dir")
    f.set_defaults(func=cmd_fetch)

    s = sub.add_parser("sync", help="scaffold every CSES problem into problems/")
    s.add_argument(
        "--category",
        help="only this folder slug, e.g. introductory or sorting_and_searching",
    )
    s.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="seconds to wait between problem fetches (default 0.2)",
    )
    s.add_argument("--dry-run", action="store_true", help="print paths, don't write")
    s.add_argument("--list", dest="list_path", metavar="PATH", help="ordered roadmap.txt list")
    s.set_defaults(func=cmd_sync)

    l = sub.add_parser("login", help="save a CSES session cookie (gitignored)")
    l.set_defaults(func=cmd_login)

    w = sub.add_parser("whoami", help="show the saved CSES username")
    w.set_defaults(func=cmd_whoami)

    r = sub.add_parser("run", help="compile/run sample tests")
    r.add_argument(
        "target",
        nargs="?",
        default=None,
        help="slug, folder, or sol.py (default: current problem folder)",
    )
    r.add_argument("--list", dest="list_path", metavar="PATH", help="run entries from an ordered roadmap.txt list")
    r.add_argument("-i", "--interactive", action="store_true", help="read stdin")
    r.add_argument(
        "--timeout",
        type=positive_float,
        default=None,
        metavar="SEC",
        help="maximum seconds per sample test (default: no timeout)",
    )
    r.set_defaults(func=cmd_run)

    u = sub.add_parser("submit", help="submit sol.cpp or sol.py and poll the verdict")
    u.add_argument(
        "target",
        nargs="?",
        default=None,
        help="slug, folder, or sol.py (default: current problem folder)",
    )
    u.add_argument("--lang", default=None, help="CSES language (default: from file)")
    u.add_argument(
        "--option",
        default=None,
        help="CSES option (default: C++17 or PyPy3)",
    )
    u.set_defaults(func=cmd_submit)

    nxt = sub.add_parser("next", help="open the next unsolved problem")
    nxt.add_argument(
        "target",
        nargs="?",
        default=None,
        help="slug, folder, or sol.py to start after (default: current problem folder)",
    )
    nxt.set_defaults(func=cmd_next)

    n = sub.add_parser("new", help="scaffold one problem folder")
    n.add_argument("category")
    n.add_argument("slug")
    n.add_argument("url", nargs="?", help="optional CSES task URL")
    n.set_defaults(func=cmd_new)

    inst = sub.add_parser("install", help="symlink cses into ~/.local/bin")
    inst.set_defaults(func=cmd_install)

    c = sub.add_parser("celebrate", help="preview the ACCEPTED animation")
    c.add_argument("--title", default="Trailing Zeros")
    c.add_argument("--score", default="13/13")
    c.set_defaults(func=cmd_celebrate)

    setup = sub.add_parser("setup", help="save local TUI preferences")
    setup.add_argument("--editor", default=None, help="editor command: code, cursor, vim, nvim, or custom")
    setup.add_argument("--session-mode", default=None, choices=("cookie", "phpseSSID"), help="preferred session mode")
    setup.add_argument("--repo-path", default=None, help="existing problems directory to sync with")
    setup.add_argument("--roadmap", default=None, help="roadmap JSON or TXT file")
    setup.set_defaults(func=cmd_setup)

    t = sub.add_parser("tui", help="launch the keyboard-first CSES Kit TUI")
    t.add_argument("--repo-path", default=None, help="existing problems directory to browse")
    t.add_argument("--roadmap", default=None, help="roadmap JSON or TXT file")
    t.set_defaults(func=cmd_tui)

    v = sub.add_parser("version", help="print the cses-kit version")
    v.set_defaults(func=cmd_version)
    return p


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
