import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import cses_lib


class CookieJarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.jar = os.path.join(self.tmp, "cookies.txt")

    def test_writes_netscape_line_with_phpsessid(self):
        cses_lib.write_cookie_jar("abc123", cookie_file=self.jar)
        with open(self.jar, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("# Netscape HTTP Cookie File", text)
        fields = [l for l in text.splitlines() if not l.startswith("#") and l.strip()]
        self.assertEqual(len(fields), 1)
        parts = fields[0].split("\t")
        self.assertEqual(parts[0], "cses.fi")
        self.assertEqual(parts[5], "PHPSESSID")
        self.assertEqual(parts[6], "abc123")

    @unittest.skipIf(sys.platform == "win32", "Windows has no Unix file modes")
    def test_file_mode_is_0600(self):
        cses_lib.write_cookie_jar("abc123", cookie_file=self.jar)
        mode = os.stat(self.jar).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_rejects_empty_session(self):
        with self.assertRaises(cses_lib.CurlError):
            cses_lib.write_cookie_jar("", cookie_file=self.jar)

    def test_rejects_session_with_spaces(self):
        with self.assertRaises(cses_lib.CurlError):
            cses_lib.write_cookie_jar("bad value", cookie_file=self.jar)


class ClearSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.jar = os.path.join(self.tmp, "cookies.txt")

    def test_removes_existing_file(self):
        cses_lib.write_cookie_jar("abc123", cookie_file=self.jar)
        self.assertTrue(cses_lib.clear_session(cookie_file=self.jar))
        self.assertFalse(os.path.exists(self.jar))

    def test_returns_false_when_missing(self):
        self.assertFalse(cses_lib.clear_session(cookie_file=self.jar))


class EnvSessionTests(unittest.TestCase):
    def test_reads_cses_phpsessid(self):
        with mock.patch.dict(os.environ, {"CSES_PHPSESSID": "xyz"}, clear=False):
            with mock.patch.object(cses_lib, "load_dotenv", lambda *a, **k: None):
                self.assertEqual(cses_lib.env_session_id(), "xyz")


class WarnPasswordDeprecatedTests(unittest.TestCase):
    def test_warns_when_password_set(self):
        buf = StringIO()
        with mock.patch.dict(os.environ, {"CSES_PASS": "hunter2"}, clear=False):
            with mock.patch.object(cses_lib, "load_dotenv", lambda *a, **k: None):
                with mock.patch.object(sys, "stderr", buf):
                    with mock.patch.object(sys.stderr, "isatty", lambda: True):
                        fired = cses_lib.warn_password_deprecated()
        self.assertTrue(fired)
        self.assertIn("deprecated", buf.getvalue())




class EnsureSessionGateTests(unittest.TestCase):
    def test_raises_when_password_login_disabled(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("CSES_ALLOW_PASSWORD_LOGIN", "CSES_PHPSESSID",
                            "CSES_NICK", "CSES_PASS")}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(cses_lib, "load_dotenv", lambda *a, **k: None):
                with mock.patch.object(cses_lib, "whoami", lambda *a, **k: None):
                    with mock.patch.object(cses_lib, "env_session_id", lambda: ""):
                        with self.assertRaises(cses_lib.CurlError) as ctx:
                            cses_lib.ensure_session(cookie_file="ignored")
        self.assertIn("CSES_ALLOW_PASSWORD_LOGIN", str(ctx.exception))


class EnsureSessionJarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.jar = os.path.join(self.tmp, "cookies.txt")

    def test_uses_existing_valid_jar(self):
        with mock.patch.object(cses_lib, "whoami", lambda *a, **k: "alice"):
            with mock.patch.object(cses_lib, "env_credentials", lambda: ("", "")):
                self.assertEqual(cses_lib.ensure_session(cookie_file=self.jar), "alice")

    def test_env_sid_writes_and_verifies(self):
        with mock.patch.object(cses_lib, "whoami", side_effect=[None, "bob"]):
            with mock.patch.object(cses_lib, "env_session_id", lambda: "sid123"):
                with mock.patch.object(cses_lib, "write_cookie_jar") as w:
                    with mock.patch.object(cses_lib, "env_credentials", lambda: ("", "")):
                        self.assertEqual(
                            cses_lib.ensure_session(cookie_file=self.jar), "bob"
                        )
                        w.assert_called_once_with("sid123", cookie_file=self.jar)

    def test_bad_env_sid_clears_and_raises(self):
        with mock.patch.object(cses_lib, "whoami", return_value=None):
            with mock.patch.object(cses_lib, "env_session_id", lambda: "bad"):
                with mock.patch.object(cses_lib, "write_cookie_jar"):
                    with mock.patch.object(cses_lib, "clear_session") as c:
                        with mock.patch.object(cses_lib, "env_credentials", lambda: ("", "")):
                            with self.assertRaises(cses_lib.CurlError):
                                cses_lib.ensure_session(cookie_file=self.jar)
                        c.assert_called_once_with(cookie_file=self.jar)


class CliHelpTests(unittest.TestCase):
    def test_help_lists_login_and_logout(self):
        script = os.path.join(os.path.dirname(__file__), "..", "scripts", "cses.py")
        out = __import__("subprocess").run(
            [sys.executable, script, "--help"],
            capture_output=True, text=True,
        )
        self.assertIn("login", out.stdout)
        self.assertIn("logout", out.stdout)

if __name__ == "__main__":
    unittest.main()
