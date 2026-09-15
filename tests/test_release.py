import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import cses_lib as lib  # noqa: E402
import release_notes  # noqa: E402


class VersionTests(unittest.TestCase):
    def test_version_file_is_semver(self):
        ver = lib.package_version()
        self.assertRegex(ver, r"^\d+\.\d+\.\d+$")
        with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
            self.assertEqual(ver, f.read().strip())

    def test_cli_version_flag_and_command(self):
        ver = lib.package_version()
        script = os.path.join(SCRIPTS, "cses.py")
        for args in (["--version"], ["-V"], ["version"]):
            proc = subprocess.run(
                [sys.executable, script, *args],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(f"cses-kit {ver}", proc.stdout)


class ReleaseNotesTests(unittest.TestCase):
    def test_tag_to_version(self):
        self.assertEqual(release_notes.tag_to_version("v0.2.1"), "0.2.1")
        self.assertEqual(release_notes.tag_to_version("1.0.0"), "1.0.0")
        with self.assertRaises(ValueError):
            release_notes.tag_to_version("v0.2")
        with self.assertRaises(ValueError):
            release_notes.tag_to_version("release-1")

    def test_changelog_section_and_check(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with open(os.path.join(tmp, "VERSION"), "w", encoding="utf-8") as f:
            f.write("0.2.1\n")
        with open(os.path.join(tmp, "CHANGELOG.md"), "w", encoding="utf-8") as f:
            f.write(
                "# Changelog\n\n"
                "## [Unreleased]\n\n"
                "## [0.2.1] - 2026-09-15\n\n"
                "### Fixed\n\n"
                "- timing on macOS\n\n"
                "## [0.2.0] - 2026-09-01\n\n"
                "### Added\n\n"
                "- Node.js\n\n"
                "[Unreleased]: https://example.com/compare/v0.2.1...HEAD\n"
                "[0.2.1]: https://example.com/releases/tag/v0.2.1\n"
            )
        notes = release_notes.notes_for_tag("v0.2.1", root=tmp)
        self.assertIn("## [0.2.1] - 2026-09-15", notes)
        self.assertIn("timing on macOS", notes)
        self.assertNotIn("Node.js", notes)
        self.assertNotIn("example.com", notes)

        with self.assertRaises(ValueError):
            release_notes.notes_for_tag("v0.9.9", root=tmp)
        with open(os.path.join(tmp, "VERSION"), "w", encoding="utf-8") as f:
            f.write("0.2.0\n")
        with self.assertRaises(ValueError):
            release_notes.notes_for_tag("v0.2.1", root=tmp)

    def test_current_changelog_has_version_heading(self):
        ver = lib.package_version()
        notes = release_notes.notes_for_tag(f"v{ver}", root=ROOT)
        self.assertIn(f"## [{ver}]", notes)
