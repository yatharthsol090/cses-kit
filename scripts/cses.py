#!/usr/bin/env python3
"""CSES local workflow: sync the problem set, log in, and submit.

Usage:
    cses sync [--category CAT] [--delay SEC] [--dry-run]
    cses login
    cses whoami
    cses run [slug|path] [-i]
    cses submit [slug|path]
    cses fetch <cses-task-url> <problem-dir>
    cses new <category> <slug> [url]
    cses install
    cses celebrate
    cses version
"""
from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cses_lib import (
    CurlError,
    celebrate as do_celebrate,
    existing_problems,
    ensure_sol_cpp,
    env_credentials,
    fetch,
    fetch_problem,
    find_problem,
    LIST_URL,
    load_dotenv,
    login as do_login,
    package_version,
    parse_problem_list,
    problem_dir_for,
    repo_root,
    slugify_category,
    submit_solution,
    whoami,
)


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
    print("listing CSES problem set …", flush=True)
    try:
        page = fetch(LIST_URL)
    except Exception as e:  # noqa: BLE001
        print(f"error: could not fetch problem list: {e}", file=sys.stderr)
        return 1
    tasks = parse_problem_list(page)
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
        dest = problem_dir_for(task, by_id)
        by_id.setdefault(task["id"], dest)
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
            title, n = fetch_problem(task["url"], dest)
            by_id[task["id"]] = dest
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
        return 0
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


def cmd_run(args: argparse.Namespace) -> int:
    try:
        path, source = find_problem(args.target)
    except CurlError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    cmd = [os.path.join(repo_root(), "scripts", "run.sh"), source or path]
    if args.interactive:
        cmd.append("-i")
    return subprocess.call(cmd)


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


def cmd_celebrate(args: argparse.Namespace) -> int:
    do_celebrate(args.title, args.score)
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    print(f"cses-kit {package_version()}")
    return 0


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
    r.add_argument("-i", "--interactive", action="store_true", help="read stdin")
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

    v = sub.add_parser("version", help="print the cses-kit version")
    v.set_defaults(func=cmd_version)
    return p


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
