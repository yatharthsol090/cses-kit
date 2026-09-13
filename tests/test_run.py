import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class RunShTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        os.makedirs(os.path.join(self.tmp, "tests"))

    def _run(self, *args):
        script = os.path.join(ROOT, "scripts", "run.sh")
        return subprocess.run(
            [script, *args],
            capture_output=True,
            text=True,
        )

    def test_python_sample_pass_and_fail(self):
        with open(os.path.join(self.tmp, "sol.py"), "w") as f:
            f.write("print(int(input()) * 2)\n")
        with open(os.path.join(self.tmp, "tests", "1.in"), "w") as f:
            f.write("21\n")
        with open(os.path.join(self.tmp, "tests", "1.out"), "w") as f:
            f.write("42\n")
        proc = self._run(os.path.join(self.tmp, "sol.py"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("passed", proc.stdout)

        with open(os.path.join(self.tmp, "tests", "1.out"), "w") as f:
            f.write("0\n")
        proc = self._run(self.tmp)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("FAIL", proc.stdout)
        self.assertIn("expected", proc.stdout)
        self.assertIn("got", proc.stdout)

    def test_run_without_bc(self):
        with open(os.path.join(self.tmp, "sol.py"), "w") as f:
            f.write("print(int(input()) * 2)\n")

        with open(os.path.join(self.tmp, "tests", "1.in"), "w") as f:
            f.write("21\n")

        with open(os.path.join(self.tmp, "tests", "1.out"), "w") as f:
            f.write("42\n")

        fake_bin = os.path.join(self.tmp, "bin")
        os.makedirs(fake_bin)

        bc = os.path.join(fake_bin, "bc")
        with open(bc, "w") as f:
            f.write("#!/bin/sh\nexit 127\n")
        os.chmod(bc, 0o755)

        env = os.environ.copy()
        env["PATH"] = fake_bin + os.pathsep + env["PATH"]

        script = os.path.join(ROOT, "scripts", "run.sh")
        proc = subprocess.run(
            [script, os.path.join(self.tmp, "sol.py")],
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("passed", proc.stdout)

    @unittest.skipUnless(shutil.which("g++"), "g++ not installed")
    def test_cpp_sample_pass(self):
        with open(os.path.join(self.tmp, "sol.cpp"), "w") as f:
            f.write(
                "#include <iostream>\nint main(){int n; std::cin>>n; std::cout<<n*2<<'\\n';}\n"
            )
        with open(os.path.join(self.tmp, "tests", "1.in"), "w") as f:
            f.write("3\n")
        with open(os.path.join(self.tmp, "tests", "1.out"), "w") as f:
            f.write("6\n")
        proc = self._run(self.tmp)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_missing_source_fails(self):
        proc = self._run(self.tmp)
        self.assertNotEqual(proc.returncode, 0)
