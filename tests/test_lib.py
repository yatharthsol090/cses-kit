import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
import sys

sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cses_lib as lib


class ParseTests(unittest.TestCase):
    def test_slugify_problem(self):
        self.assertEqual(lib.slugify_problem("Missing Number"), "missing-number")
        self.assertEqual(lib.slugify_problem("Trailing Zeros"), "trailing-zeros")

    def test_slugify_category(self):
        self.assertEqual(lib.slugify_category("Introductory Problems"), "introductory")
        self.assertEqual(
            lib.slugify_category("Sorting and Searching"), "sorting_and_searching"
        )

    def test_parse_problem_list_skips_general(self):
        page = """
        <h2>General</h2>
        <a href="/problemset/task/1">Intro</a>
        <h2>Introductory Problems</h2>
        <a href="/problemset/task/1068">Weird Algorithm</a>
        <a href="/problemset/task/1083">Missing Number</a>
        """
        tasks = lib.parse_problem_list(page)
        self.assertEqual([t["id"] for t in tasks], ["1068", "1083"])
        self.assertEqual(tasks[0]["slug"], "weird-algorithm")
        self.assertEqual(tasks[0]["category"], "introductory")
        self.assertTrue(tasks[0]["url"].endswith("/task/1068"))

    def test_parse_statement_and_samples(self):
        page = """
        <title>CSES - Trailing Zeros</title>
        <ul class="task-constraints">
        <li>Time limit: 1.00 s</li>
        <li>Memory limit: 512 MB</li>
        </ul>
        <div class="md"><p>Count trailing zeros in n!.</p></div>
        <div id="example"></div>
        <pre>20</pre>
        <pre>4</pre>
        <div class="nav sidebar"></div>
        """
        title, md, tests = lib.parse_statement(page, "https://cses.fi/problemset/task/1618")
        self.assertEqual(title, "Trailing Zeros")
        self.assertIn("**Link:** https://cses.fi/problemset/task/1618", md)
        self.assertIn("1.00 s", md)
        self.assertEqual(tests, [("20\n", "4\n")])

    def test_parse_result_page_and_details(self):
        page = """
        <tr><td>Result:</td><td>WRONG ANSWER</td></tr>
        <tr><td>Task:</td><td>Trailing Zeros</td></tr>
        <tr>
          <td>1</td>
          <td class="inline-score verdict wa">WRONG ANSWER</td>
          <td>0.00 s</td>
        </tr>
        <h4 id="test1">Test 1</h4>
        <p>Verdict: WRONG ANSWER</p>
        <table>
        <tr><th>input</th></tr>
        <tr><td><samp>395</samp></td></tr>
        <tr><th>correct output</th></tr>
        <tr><td><samp>97</samp></td></tr>
        <tr><th>user output</th></tr>
        <tr><td><samp>103</samp></td></tr>
        </table>
        Feedback: expected "97", got "103"<br/>
        """
        info = lib.parse_result_page(page)
        self.assertEqual(info["Result"], "WRONG ANSWER")
        self.assertEqual(info["tests"][0], "#1  WRONG ANSWER  0.00 s")
        self.assertEqual(info["test_times"]["1"], "0.00 s")
        d = info["test_details"][0]
        self.assertEqual(d["input"], "395")
        self.assertEqual(d["expected"], "97")
        self.assertEqual(d["got"], "103")
        self.assertIn("97", d["feedback"])

    def test_derive_verdict_and_score(self):
        wa = {"Result": "WRONG ANSWER (2/13)", "tests": ["#1  WRONG ANSWER  0.00 s", "#2  ACCEPTED  0.00 s"]}
        self.assertEqual(lib.derive_verdict(wa, "READY"), "WRONG ANSWER")
        self.assertEqual(lib.test_score(wa), "1/2")
        ac = {"Result": "ACCEPTED", "tests": ["#1  ACCEPTED  0.01 s"]}
        self.assertEqual(lib.derive_verdict(ac, "READY"), "ACCEPTED")

    def test_task_id_from_text(self):
        self.assertEqual(
            lib.task_id_from_text("**Link:** https://cses.fi/problemset/task/1618"),
            "1618",
        )
        self.assertIsNone(lib.task_id_from_text("no link here"))


class SourceAndPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _prob(self, slug="demo"):
        d = os.path.join(self.tmp, "problems", "introductory", slug)
        os.makedirs(os.path.join(d, "tests"), exist_ok=True)
        with open(os.path.join(d, "statement.md"), "w") as f:
            f.write("# Demo\n\n**Link:** https://cses.fi/problemset/task/1618\n")
        return d

    def test_pick_python_when_cpp_is_template(self):
        d = self._prob()
        shutil.copy(os.path.join(ROOT, "template.cpp"), os.path.join(d, "sol.cpp"))
        with open(os.path.join(d, "sol.py"), "w") as f:
            f.write("print(1)\n")
        self.assertTrue(lib.sol_looks_like_template(os.path.join(d, "sol.cpp")))
        self.assertTrue(lib.pick_source_file(d).endswith("sol.py"))
        _, lang, opt = lib.resolve_source(d)
        self.assertEqual((lang, opt), ("Python3", "PyPy3"))

    def test_pick_cpp_when_it_is_a_real_solution(self):
        d = self._prob()
        with open(os.path.join(d, "sol.cpp"), "w") as f:
            f.write("#include <iostream>\nint main(){std::cout<<1;}\n")
        with open(os.path.join(d, "sol.py"), "w") as f:
            f.write("print(1)\n")
        self.assertTrue(lib.pick_source_file(d).endswith("sol.cpp"))
        path, lang, opt = lib.resolve_source(d, source=os.path.join(d, "sol.py"))
        self.assertEqual((lang, opt), ("Python3", "PyPy3"))
        self.assertTrue(path.endswith("sol.py"))

    def test_solution_with_placeholder_is_not_template(self):
        d = self._prob()
        template_path = os.path.join(ROOT, "template.cpp")
        solution_path = os.path.join(d, "sol.cpp")
        with open(template_path, encoding="utf-8") as f:
            source = f.read().replace(
                "    // ---- your solution goes here ----\n\n",
                "    // ---- your solution goes here ----\n    int n;\n    cin >> n;\n",
            )
        with open(solution_path, "w", encoding="utf-8") as f:
            f.write(source)
        self.assertFalse(lib.sol_looks_like_template(solution_path))

    def test_no_solution_is_an_error(self):
        d = self._prob()
        with self.assertRaises(lib.CurlError):
            lib.pick_source_file(d)

    def test_find_problem_by_slug_and_cwd(self):
        d = self._prob("trailing-zeroes")
        with patch.object(lib, "repo_root", return_value=self.tmp):
            got, src = lib.find_problem("trailing-zeroes")
            self.assertEqual(os.path.realpath(got), os.path.realpath(d))
            self.assertIsNone(src)
            with self.assertRaises(lib.CurlError):
                lib.find_problem("trailing-zeroes/sol.py")
        with open(os.path.join(d, "sol.py"), "w") as f:
            f.write("print(1)\n")
        with patch.object(lib, "repo_root", return_value=self.tmp):
            got, src = lib.find_problem("trailing-zeroes/sol.py")
            self.assertTrue(src.endswith("sol.py"))
            self.assertIsNone(lib.problem_from_cwd(self.tmp))
            self.assertEqual(
                os.path.realpath(lib.problem_from_cwd(d)), os.path.realpath(d)
            )
            here = os.getcwd()
            try:
                os.chdir(d)
                got, src = lib.find_problem(None)
                self.assertEqual(os.path.realpath(got), os.path.realpath(d))
            finally:
                os.chdir(here)

    def test_find_problem_unknown_slug(self):
        with patch.object(lib, "repo_root", return_value=self.tmp):
            with self.assertRaises(lib.CurlError):
                lib.find_problem("does-not-exist")

    def test_unsupported_extension(self):
        d = self._prob()
        rs = os.path.join(d, "sol.rs")
        open(rs, "w").close()
        with self.assertRaises(lib.CurlError):
            lib.resolve_source(d, source=rs)


class ReportTests(unittest.TestCase):
    def test_format_card_and_first_failure(self):
        info = {
            "test_details": [
                {
                    "num": "1",
                    "verdict": "WRONG ANSWER",
                    "input": "20",
                    "expected": "4",
                    "got": "5",
                    "feedback": "mismatch",
                }
            ],
            "test_times": {"1": "0.00 s"},
        }
        fail = lib.first_failed_test(info)
        self.assertEqual(fail["num"], "1")
        card = "\n".join(lib.format_test_card(fail, "0.00 s"))
        self.assertIn("FAIL", card)
        self.assertIn("20", card)
        table = "\n".join(lib.format_summary_table(info))
        self.assertIn("WRONG ANSWER", table)

    def test_write_submit_report_and_record_verdict(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        stmt = os.path.join(tmp, "statement.md")
        with open(stmt, "w") as f:
            f.write("# Demo\n\n**Link:** https://cses.fi/problemset/task/1\n")
        info = {
            "Task": "Demo",
            "Submission time": "now",
            "Language": "Python3 (PyPy3)",
            "tests": ["#1  WRONG ANSWER  0.00 s"],
            "test_times": {"1": "0.00 s"},
            "test_details": [
                {
                    "num": "1",
                    "verdict": "WRONG ANSWER",
                    "input": "1",
                    "expected": "2",
                    "got": "3",
                    "feedback": "nope",
                }
            ],
        }
        path = lib.write_submit_report(tmp, "99", "WRONG ANSWER", "0/1", info)
        text = open(path).read()
        self.assertIn("Submission  99", text)
        self.assertIn("expected", text)
        self.assertIn("3", text)
        line = lib.record_verdict(tmp, "WRONG ANSWER", "99", info)
        self.assertIn("WRONG ANSWER", line)
        self.assertIn("**Verdict:**", open(stmt).read())


class DotenvTests(unittest.TestCase):
    def test_load_dotenv_does_not_override(self):
        tmp = tempfile.NamedTemporaryFile("w", delete=False)
        tmp.write("CSES_NICK=fromfile\nCSES_PASS='secret'\n")
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        keys = ("CSES_NICK", "CSES_PASS", "CSES_USER", "CSES_USERNAME", "CSES_PASSWORD")
        with patch.dict(os.environ, {"CSES_NICK": "already"}, clear=False):
            lib.load_dotenv(tmp.name)
            self.assertEqual(os.environ.get("CSES_NICK"), "already")
        with patch.dict(os.environ, {k: "" for k in keys}, clear=False):
            for k in keys:
                os.environ.pop(k, None)
            lib.load_dotenv(tmp.name)
            self.assertEqual(os.environ.get("CSES_NICK"), "fromfile")
            self.assertEqual(os.environ.get("CSES_PASS"), "secret")


class NextUnsolvedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        p1 = os.path.join(self.tmp, "problems", "intro", "prob1")
        p2 = os.path.join(self.tmp, "problems", "intro", "prob2")
        os.makedirs(p1)
        os.makedirs(p2)
        with open(os.path.join(p1, "statement.md"), "w") as f:
            f.write("# Prob 1\n**Link:** https://cses.fi/problemset/task/101\n**Verdict:** ACCEPTED\n")
        with open(os.path.join(p2, "statement.md"), "w") as f:
            f.write("# Prob 2\n**Link:** https://cses.fi/problemset/task/102\n")

        self.tasks = [
            {"id": "101", "name": "Prob 1", "slug": "prob1", "category": "intro", "url": "https://cses.fi/problemset/task/101"},
            {"id": "102", "name": "Prob 2", "slug": "prob2", "category": "intro", "url": "https://cses.fi/problemset/task/102"},
        ]
        self.existing = {
            "101": p1,
            "102": p2,
        }

    def test_next_unsolved_from_none(self):
        with patch.object(lib, "fetch", return_value=""), patch.object(
            lib, "parse_problem_list", return_value=self.tasks
        ), patch.object(lib, "existing_problems", return_value=self.existing), patch.object(
            lib, "repo_root", return_value=self.tmp
        ):
            res = lib.next_unsolved(None)
            self.assertEqual(res, os.path.relpath(self.existing["102"], self.tmp))

    def test_next_unsolved_from_current(self):
        with patch.object(lib, "fetch", return_value=""), patch.object(
            lib, "parse_problem_list", return_value=self.tasks
        ), patch.object(lib, "existing_problems", return_value=self.existing), patch.object(
            lib, "repo_root", return_value=self.tmp
        ):
            res = lib.next_unsolved(self.existing["101"])
            self.assertEqual(res, os.path.relpath(self.existing["102"], self.tmp))

    def test_next_unsolved_all_accepted(self):
        with open(os.path.join(self.existing["102"], "statement.md"), "w") as f:
            f.write("# Prob 2\n**Link:** https://cses.fi/problemset/task/102\n**Verdict:** ACCEPTED\n")
        with patch.object(lib, "fetch", return_value=""), patch.object(
            lib, "parse_problem_list", return_value=self.tasks
        ), patch.object(lib, "existing_problems", return_value=self.existing), patch.object(
            lib, "repo_root", return_value=self.tmp
        ):
            res = lib.next_unsolved(None)
            self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
