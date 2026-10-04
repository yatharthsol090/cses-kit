import json
import os
import shutil
import tempfile
import unittest

from scripts.roadmap import (
    build_problem_index_from_tasks,
    build_default_roadmap,
    load_problem_index,
    load_roadmap,
    parse_roadmap_json,
    parse_roadmap_txt,
)


class RoadmapTests(unittest.TestCase):
    def test_parse_json_roadmap_preserves_order(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump([
                {"id": 1068, "name": "Weird Algorithm", "category": "introductory", "url": "https://cses.fi/problemset/task/1068"},
                {"id": 1083, "name": "Missing Number", "category": "introductory", "url": "https://cses.fi/problemset/task/1083"},
            ], f)
            path = f.name
        try:
            items = parse_roadmap_json(path)
            self.assertEqual([item["id"] for item in items], [1068, 1083])
        finally:
            os.unlink(path)

    def test_parse_txt_roadmap_accepts_id_url_or_slug(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("1068\nhttps://cses.fi/problemset/task/1083\ntrailing-zeroes\n")
            path = f.name
        try:
            items = parse_roadmap_txt(path)
            self.assertEqual(items[0]["id"], "1068")
            self.assertEqual(items[1]["id"], "1083")
            self.assertEqual(items[2]["slug"], "trailing-zeroes")
        finally:
            os.unlink(path)

    def test_parse_txt_roadmap_preserves_order(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("# comment\n\n1068 https://cses.fi/problemset/task/1068 weird-algorithm\n1083 https://cses.fi/problemset/task/1083 missing-number\n")
            path = f.name
        try:
            items = parse_roadmap_txt(path)
            self.assertEqual([item["id"] for item in items], ["1068", "1083"])
        finally:
            os.unlink(path)

    def test_parse_txt_unknown_line_reports_location(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("1068 https://cses.fi/problemset/task/1068 weird-algorithm\nnot a roadmap record\n")
            path = f.name
        try:
            with self.assertRaisesRegex(ValueError, rf"{path}:2: unknown roadmap line"):
                parse_roadmap_txt(path)
        finally:
            os.unlink(path)

    def test_load_roadmap_dispatches_by_extension(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump([{"id": 1, "name": "A", "category": "custom", "url": "https://cses.fi/problemset/task/1"}], f)
            path = f.name
        try:
            items = load_roadmap(path)
            self.assertEqual(items[0]["name"], "A")
        finally:
            os.unlink(path)

    def test_build_default_roadmap_uses_source_order(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("Introductory Problems\n[\n  {\n    \"a\": \"Weird Algorithm\",\n    \"a_link\": \"https://cses.fi/problemset/task/1068\"\n  },\n  {\n    \"a\": \"Missing Number\",\n    \"a_link\": \"https://cses.fi/problemset/task/1083\"\n  }\n]\n")
            path = f.name
        try:
            items = build_default_roadmap(path)
            self.assertEqual([item["id"] for item in items], [1068, 1083])
            self.assertEqual(items[0]["category"], "Introductory Problems")
        finally:
            os.unlink(path)

    def test_build_default_roadmap_parses_mixed_interactive_section(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write(
                "Interactive Problems\n"
                "Hidden Integer\nhttps://cses.fi/problemset/task/3112\n"
                "Bitwise Operations\n[\n"
                '{"a": "Counting Bits", "a_link": "https://cses.fi/problemset/task/1146"}\n'
                "]\nConstruction Problems\n[\n"
                '{"a": "Inverse Inversions", "a_link": "https://cses.fi/problemset/task/2214"}\n'
                "]\n"
            )
            path = f.name
        try:
            items = build_default_roadmap(path)
            self.assertEqual({item["id"] for item in items}, {3112, 1146, 2214})
        finally:
            os.unlink(path)

    def test_problem_index_is_keyed_by_task_id(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({
                "1068": {
                    "id": 1068,
                    "name": "Weird Algorithm",
                    "category": "Introductory Problems",
                    "url": "https://cses.fi/problemset/task/1068",
                    "downloaded": False,
                    "solved": False,
                }
            }, f)
            path = f.name
        try:
            index = load_problem_index(path)
            self.assertEqual(index["https://cses.fi/problemset/task/1068"]["url"], "https://cses.fi/problemset/task/1068")
        finally:
            os.unlink(path)

    def test_problem_index_contains_task_metadata(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        index = build_problem_index_from_tasks([
            {
                "id": "1068",
                "title": "Weird Algorithm",
                "section": "Introductory Problems",
                "category": "introductory",
                "url": "https://cses.fi/problemset/task/1068",
            }
        ], repo_root=root)
        self.assertEqual(index[0]["link"], "https://cses.fi/problemset/task/1068")
        self.assertEqual(index[0]["name"], "Weird Algorithm")
