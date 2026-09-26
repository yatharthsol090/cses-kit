import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cses_lib as lib


class TemplateDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fallback = self.root / "template.cpp"
        self.fallback.write_text("// fallback\n", encoding="utf-8")
        self.preferred = self.root / "templates/cpp/template.cpp"
        self.preferred.parent.mkdir(parents=True)
        self.preferred.write_text("// custom starter\n", encoding="utf-8")
        root_patch = patch.object(lib, "repo_root", return_value=str(self.root))
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def test_new_solution_uses_preferred_template_and_is_recognized(self):
        problem = self.root / "problem"
        lib.ensure_sol_cpp(str(problem))
        source = problem / "sol.cpp"
        self.assertEqual(source.read_bytes(), self.preferred.read_bytes())
        self.assertTrue(lib.sol_looks_like_template(str(source)))
        (problem / "sol.py").write_text("print(42)\n", encoding="utf-8")
        self.assertEqual(lib.pick_source_file(str(problem)), str(problem / "sol.py"))

    def test_root_template_remains_a_fallback(self):
        self.preferred.unlink()
        problem = self.root / "problem"
        lib.ensure_sol_cpp(str(problem))
        self.assertEqual((problem / "sol.cpp").read_bytes(), self.fallback.read_bytes())

    def test_existing_solution_is_preserved(self):
        problem = self.root / "problem"
        problem.mkdir()
        source = problem / "sol.cpp"
        source.write_text("int main() { return 0; }\n", encoding="utf-8")
        lib.ensure_sol_cpp(str(problem))
        self.assertEqual(source.read_text(), "int main() { return 0; }\n")

    @unittest.skipUnless(os.name == "posix", "run.sh requires a POSIX shell")
    def test_runner_recognizes_the_custom_template(self):
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copyfile(ROOT / "scripts/run.sh", scripts / "run.sh")
        problem = self.root / "problem"
        lib.ensure_sol_cpp(str(problem))
        (problem / "sol.py").write_text("print(42)\n", encoding="utf-8")
        (problem / "tests").mkdir()
        (problem / "tests/1.in").write_text("", encoding="utf-8")
        (problem / "tests/1.out").write_text("42\n", encoding="utf-8")
        result = subprocess.run(["bash", str(scripts / "run.sh"), str(problem)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("python3", result.stdout)
        self.assertIn("1 passed", result.stdout)
