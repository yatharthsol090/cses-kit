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
        for cmd in ("sync", "run", "submit", "login", "new", "fetch", "version"):
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
