import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import cses as cses_cli  # noqa: E402
import cses_lib as lib  # noqa: E402


class CliTests(unittest.TestCase):
    def test_help_lists_commands(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "cses.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        for cmd in ("sync", "run", "submit", "login", "new", "fetch", "status", "version"):
            self.assertIn(cmd, proc.stdout)

    def test_missing_subcommand_fails(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "cses.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)

    def test_run_unknown_problem_fails(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "cses.py"), "run", "no-such-slug-xyz"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("error", proc.stderr.lower())

    def test_parser_submit_optional_target(self):
        p = cses_cli.build_parser()
        args = p.parse_args(["submit"])
        self.assertIsNone(args.target)
        args = p.parse_args(["submit", "trailing-zeroes/sol.py"])
        self.assertEqual(args.target, "trailing-zeroes/sol.py")

    def test_parser_run_timeout(self):
        p = cses_cli.build_parser()
        args = p.parse_args(["run", "--timeout", "1.5", "trailing-zeroes"])
        self.assertEqual(args.timeout, 1.5)
        with self.assertRaises(SystemExit):
            p.parse_args(["run", "--timeout", "0"])

    def test_cmd_new_without_url(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copy(os.path.join(ROOT, "template.cpp"), os.path.join(tmp, "template.cpp"))
        ns = argparse.Namespace(category="intro", slug="hello", url=None)
        buf = __import__("io").StringIO()
        with patch.object(lib, "repo_root", return_value=tmp), patch.object(
            cses_cli, "repo_root", return_value=tmp
        ), patch("sys.stdout", buf), patch("sys.stderr", buf):
            rc = cses_cli.cmd_new(ns)
            self.assertEqual(rc, 0)
            dest = os.path.join(tmp, "problems", "intro", "hello")
            self.assertTrue(os.path.isfile(os.path.join(dest, "sol.cpp")))
            self.assertTrue(os.path.isfile(os.path.join(dest, "statement.md")))
            rc = cses_cli.cmd_new(ns)
            self.assertEqual(rc, 2)

    def test_parser_status_arguments(self):
        p = cses_cli.build_parser()
        args = p.parse_args(["status"])
        self.assertIsNone(args.category)
        self.assertFalse(args.unsolved)
        self.assertFalse(args.json)

        args = p.parse_args(["status", "-c", "introductory", "-u", "--json"])
        self.assertEqual(args.category, "introductory")
        self.assertTrue(args.unsolved)
        self.assertTrue(args.json)

    def test_cmd_status_empty(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        ns = argparse.Namespace(category=None, unsolved=False, json=False)
        buf = __import__("io").StringIO()
        with patch.object(lib, "repo_root", return_value=tmp), patch.object(
            cses_cli, "repo_root", return_value=tmp
        ), patch("sys.stdout", buf):
            rc = cses_cli.cmd_status(ns)
            self.assertEqual(rc, 0)
            self.assertIn("no problems found", buf.getvalue())

    def test_cmd_status_with_problems_and_json(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        prob = os.path.join(tmp, "problems", "introductory", "weird-algorithm")
        os.makedirs(prob)
        with open(os.path.join(prob, "statement.md"), "w", encoding="utf-8") as f:
            f.write("# Weird Algorithm\n\n**Verdict:** ACCEPTED\n")

        buf = __import__("io").StringIO()
        ns = argparse.Namespace(category=None, unsolved=False, json=True)
        with patch.object(lib, "repo_root", return_value=tmp), patch.object(
            cses_cli, "repo_root", return_value=tmp
        ), patch("sys.stdout", buf):
            rc = cses_cli.cmd_status(ns)
            self.assertEqual(rc, 0)
            import json

            data = json.loads(buf.getvalue())
            self.assertEqual(data["total_solved"], 1)
            self.assertEqual(data["total_problems"], 1)
            self.assertIn("introductory", data["categories"])

