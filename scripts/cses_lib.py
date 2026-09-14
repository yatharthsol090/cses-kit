#!/usr/bin/env python3
"""Shared helpers for talking to cses.fi (stdlib + curl only)."""
from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
from typing import Iterable

UA = "Mozilla/5.0 (cses-local)"
BASE = "https://cses.fi"
LIST_URL = f"{BASE}/problemset/list/"
LOGIN_URL = f"{BASE}/login"
SEND_URL = f"{BASE}/course/send.php"
STATUS_URL = f"{BASE}/ajax/get_status.php"

# Match the folders already in this repo; everything else is a slug of the
# CSES section title ("Sorting and Searching" -> sorting_and_searching).
CATEGORY_SLUGS = {
    "Introductory Problems": "introductory",
}

# CSES <select name="lang|option"> values from the submit form.
LANG_BY_EXT = {
    ".cpp": ("C++", "C++17"),
    ".cc": ("C++", "C++17"),
    ".cxx": ("C++", "C++17"),
    ".py": ("Python3", "PyPy3"),
}


def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def cookie_path() -> str:
    d = os.path.join(repo_root(), ".cses")
    os.makedirs(d, mode=0o700, exist_ok=True)
    return os.path.join(d, "cookies.txt")


def dotenv_path() -> str:
    return os.path.join(repo_root(), ".env")


def load_dotenv(path: str | None = None) -> None:
    """Load KEY=VALUE pairs from .env into os.environ (does not override)."""
    path = path or dotenv_path()
    try:
        raw = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.lower().startswith("export "):
            s = s[7:].strip()
        if "=" not in s:
            continue
        key, val = s.split("=", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


def env_credentials() -> tuple[str, str]:
    load_dotenv()
    nick = (
        os.environ.get("CSES_NICK")
        or os.environ.get("CSES_USER")
        or os.environ.get("CSES_USERNAME")
        or ""
    ).strip()
    password = os.environ.get("CSES_PASS") or os.environ.get("CSES_PASSWORD") or ""
    return nick, password


def ensure_session(cookie_file: str | None = None) -> str:
    """Return the logged-in username, logging in from .env if needed."""
    cookie_file = cookie_file or cookie_path()
    name = whoami(cookie_file)
    if name:
        return name
    nick, password = env_credentials()
    if not nick or not password:
        raise CurlError(
            "not logged in — set CSES_NICK and CSES_PASS in .env, or run: cses login"
        )
    print("logging in from .env …", flush=True)
    return login(nick, password, cookie_file=cookie_file)


def template_cpp() -> str:
    return os.path.join(repo_root(), "template.cpp")


def template_py() -> str:
    return os.path.join(repo_root(), "template.py")


def template_for(path: str) -> str | None:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".cpp", ".cc", ".cxx"}:
        return template_cpp()
    if ext == ".py":
        return template_py()
    return None


# ---------------------------------------------------------------------------
# HTTP via curl (macOS python.org builds often can't verify TLS)
# ---------------------------------------------------------------------------

class CurlError(RuntimeError):
    pass


def _curl(
    url: str,
    *,
    method: str = "GET",
    data: dict[str, str] | None = None,
    form: list[tuple[str, str]] | None = None,
    upload: tuple[str, str] | None = None,
    cookie_file: str | None = None,
    referer: str | None = None,
    timeout: int = 30,
) -> tuple[int, str, str]:
    """Return (status_code, final_url, body)."""
    if not shutil.which("curl"):
        raise CurlError("curl is required")

    with tempfile.NamedTemporaryFile(prefix="cses_", suffix=".hdr", delete=False) as hf:
        hdr_path = hf.name
    try:
        cmd = [
            "curl", "-sS", "-L",
            "-A", UA,
            "--max-time", str(timeout),
            "-D", hdr_path,
            "-o", "-",
            "-w", "\n__CSSES_FINAL_URL__:%{url_effective}\n__CSSES_HTTP__:%{http_code}",
        ]
        if cookie_file:
            cmd += ["-b", cookie_file, "-c", cookie_file]
        if referer:
            cmd += ["-e", referer]
        if data is not None:
            cmd += ["-X", "POST"]
            for k, v in data.items():
                cmd += ["--data-urlencode", f"{k}={v}"]
        if form is not None or upload is not None:
            cmd += ["-X", "POST"]
            for k, v in form or []:
                cmd += ["-F", f"{k}={v}"]
            if upload is not None:
                field, path = upload
                cmd += ["-F", f"{field}=@{path};filename={os.path.basename(path)}"]
        elif method != "GET" and data is None and form is None:
            cmd += ["-X", method]
        cmd.append(url)

        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", "replace").strip() or f"curl exit {proc.returncode}"
            raise CurlError(err)
        raw = proc.stdout.decode("utf-8", "replace")
        final = url
        code = 0
        body = raw
        m_url = re.search(r"\n__CSSES_FINAL_URL__:(.*?)\n__CSSES_HTTP__:(\d+)\s*$", raw)
        if m_url:
            body = raw[: m_url.start()]
            final = m_url.group(1).strip()
            code = int(m_url.group(2))
        if code == 0:
            # Last non-empty HTTP status in the dumped header block.
            try:
                hdr = open(hdr_path, "r", encoding="utf-8", errors="replace").read()
            except OSError:
                hdr = ""
            codes = re.findall(r"^HTTP/\S+\s+(\d+)", hdr, flags=re.M)
            if codes:
                code = int(codes[-1])
        return code, final, body
    finally:
        try:
            os.unlink(hdr_path)
        except OSError:
            pass


def fetch(url: str, *, cookie_file: str | None = None, retries: int = 3) -> str:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            code, _, body = _curl(url, cookie_file=cookie_file)
            if code >= 400:
                raise CurlError(f"HTTP {code} for {url}")
            if body:
                return body
            raise CurlError(f"empty response from {url}")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.4 * (attempt + 1))
    raise last  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Statement parsing
# ---------------------------------------------------------------------------

def slice_between(s: str, start_pat: str, end: str) -> str:
    m = re.search(start_pat, s)
    if not m:
        return ""
    i = m.end()
    j = s.find(end, i)
    return s[i:j] if j != -1 else s[i:]


_LATEX = {
    r"\ldots": "…", r"\cdots": "…", r"\dots": "…", r"\vdots": "⋮",
    r"\cdot": "·", r"\times": "×", r"\div": "÷", r"\pm": "±", r"\mp": "∓",
    r"\leq": "≤", r"\le": "≤", r"\geq": "≥", r"\ge": "≥",
    r"\neq": "≠", r"\ne": "≠", r"\approx": "≈", r"\equiv": "≡",
    r"\infty": "∞", r"\to": "→", r"\rightarrow": "→", r"\leftarrow": "←",
    r"\in": "∈", r"\mid": "|", r"\bmod": "mod", r"\%": "%",
    r"\{": "{", r"\}": "}", r"\,": " ", r"\;": " ", r"\!": "", r"\ ": " ",
    r"\left": "", r"\right": "", r"\lfloor": "⌊", r"\rfloor": "⌋",
    r"\lceil": "⌈", r"\rceil": "⌉",
}
_SUP = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
_SUB = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")


def prettify_math(expr: str) -> str:
    s = expr
    for k in sorted(_LATEX, key=len, reverse=True):
        s = s.replace(k, _LATEX[k])
    s = re.sub(r"\^\{([^{}]*)\}", lambda m: m.group(1).translate(_SUP), s)
    s = re.sub(r"\^(\w)", lambda m: m.group(1).translate(_SUP), s)
    s = re.sub(r"_\{([^{}]*)\}", lambda m: m.group(1).translate(_SUB), s)
    s = re.sub(r"_(\w)", lambda m: m.group(1).translate(_SUB), s)
    return s


def _inline_math(m: re.Match) -> str:
    raw = m.group(1).strip()
    pretty = prettify_math(raw).strip()
    if re.search(r"[\\{}^_]", pretty):
        return f"${raw}$"
    return pretty


def md_from_div(md_html: str) -> str:
    s = md_html
    s = re.sub(r'<span class="math math-inline">(.*?)</span>', _inline_math, s, flags=re.S)
    s = re.sub(
        r'<span class="math math-display">(.*?)</span>',
        lambda m: "$$" + m.group(1).strip() + "$$",
        s,
        flags=re.S,
    )
    s = re.sub(r"<pre>(.*?)</pre>", lambda m: "\n```\n" + m.group(1).strip("\n") + "\n```\n", s, flags=re.S)
    s = re.sub(r"<code>(.*?)</code>", r"`\1`", s, flags=re.S)
    s = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n## \1\n", s, flags=re.S)
    s = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n### \1\n", s, flags=re.S)
    s = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n#### \1\n", s, flags=re.S)
    s = re.sub(r"<(b|strong)>(.*?)</\1>", r"**\2**", s, flags=re.S)
    s = re.sub(r"<(i|em)>(.*?)</\1>", r"*\2*", s, flags=re.S)
    s = re.sub(r"<li>(.*?)</li>", r"- \1", s, flags=re.S)
    s = re.sub(r"</?ul>", "", s)
    s = re.sub(r"</?ol>", "", s)
    s = re.sub(r"<p>(.*?)</p>", r"\1\n", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip() + "\n"


def extract_tests(page: str) -> list[tuple[str, str]]:
    ex = page.find('id="example"')
    region = page[ex:] if ex != -1 else page
    stop = region.find('class="nav sidebar"')
    if stop != -1:
        region = region[:stop]
    blocks = re.findall(r"<pre>(.*?)</pre>", region, flags=re.S)
    blocks = [html.unescape(b).strip("\n") + "\n" for b in blocks]
    pairs = []
    for k in range(0, len(blocks) - 1, 2):
        pairs.append((blocks[k], blocks[k + 1]))
    return pairs


def parse_statement(page: str, url: str) -> tuple[str, str, list[tuple[str, str]]]:
    title_m = re.search(r"<title>CSES - (.*?)</title>", page)
    title = html.unescape(title_m.group(1).strip()) if title_m else "Problem"
    limits_html = slice_between(page, r'<ul class="task-constraints">', "</ul>")
    items = re.findall(r"<li>(.*?)</li>", limits_html, flags=re.S)
    items = [html.unescape(re.sub(r"<[^>]+>", "", it)).strip() for it in items]
    limits = " · ".join(it for it in items if it)
    md_div = slice_between(page, r'<div class="md">', "</div>")
    body = md_from_div(md_div) if md_div else "_Could not parse statement automatically._\n"
    header = f"# {title}\n\n**Link:** {url}\n"
    if limits:
        header += f"\n**Limits:** {limits}\n"
    return title, header + "\n" + body, extract_tests(page)


def write_statement_and_tests(out_dir: str, url: str, page: str) -> tuple[str, int]:
    title, statement, tests = parse_statement(page, url)
    os.makedirs(os.path.join(out_dir, "tests"), exist_ok=True)
    with open(os.path.join(out_dir, "statement.md"), "w") as f:
        f.write(statement)
    if not tests:
        in_path = os.path.join(out_dir, "tests", "1.in")
        out_path = os.path.join(out_dir, "tests", "1.out")
        if not os.path.exists(in_path):
            open(in_path, "a").close()
        if not os.path.exists(out_path):
            open(out_path, "a").close()
        return title, 0
    for idx, (inp, outp) in enumerate(tests, start=1):
        with open(os.path.join(out_dir, "tests", f"{idx}.in"), "w") as f:
            f.write(inp)
        with open(os.path.join(out_dir, "tests", f"{idx}.out"), "w") as f:
            f.write(outp)
    return title, len(tests)


def fetch_problem(url: str, out_dir: str) -> tuple[str, int]:
    page = fetch(url)
    return write_statement_and_tests(out_dir, url, page)


# ---------------------------------------------------------------------------
# Catalog / paths
# ---------------------------------------------------------------------------

def slugify_problem(title: str) -> str:
    s = html.unescape(title).lower()
    s = s.replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "problem"


def slugify_category(section: str) -> str:
    if section in CATEGORY_SLUGS:
        return CATEGORY_SLUGS[section]
    s = section.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "misc"


def parse_problem_list(page: str) -> list[dict[str, str]]:
    parts = re.split(r"<h2>(.*?)</h2>", page, flags=re.S)
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for i in range(1, len(parts) - 1, 2):
        section = html.unescape(re.sub(r"<[^>]+>", "", parts[i])).strip()
        if section.lower() == "general":
            continue
        body = parts[i + 1]
        cat = slugify_category(section)
        for m in re.finditer(r'href="/problemset/task/(\d+)/?"[^>]*>([^<]+)', body):
            tid = m.group(1)
            if tid in seen:
                continue
            seen.add(tid)
            title = html.unescape(m.group(2)).strip()
            out.append(
                {
                    "id": tid,
                    "title": title,
                    "section": section,
                    "category": cat,
                    "slug": slugify_problem(title),
                    "url": f"{BASE}/problemset/task/{tid}",
                }
            )
    return out


def task_id_from_text(text: str) -> str | None:
    m = re.search(r"cses\.fi/problemset/(?:task|submit|view)/(\d+)", text)
    return m.group(1) if m else None


def existing_problems() -> dict[str, str]:
    """Map CSES task id -> problem directory, from existing statement.md files."""
    found: dict[str, str] = {}
    for dirpath in iter_problem_dirs():
        path = os.path.join(dirpath, "statement.md")
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        tid = task_id_from_text(text)
        if tid:
            found[tid] = dirpath
    return found


def iter_problem_dirs() -> list[str]:
    root = os.path.join(repo_root(), "problems")
    out: list[str] = []
    if not os.path.isdir(root):
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "tests"]
        if "statement.md" in filenames:
            out.append(dirpath)
    return out


def is_problem_dir(path: str) -> bool:
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, "statement.md"))


def problem_from_cwd(start: str | None = None) -> str | None:
    cur = os.path.realpath(start or os.getcwd())
    root = os.path.realpath(repo_root())
    problems = os.path.join(root, "problems")
    while True:
        if is_problem_dir(cur) and (
            cur == problems or cur.startswith(problems + os.sep)
        ):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur or os.path.abspath(cur) == root:
            return None
        cur = parent


def find_problem(spec: str | None) -> tuple[str, str | None]:
    """Resolve a folder, slug, or source file to (problem_dir, source_or_None)."""
    if spec in (None, "", "."):
        d = problem_from_cwd()
        if not d:
            raise CurlError(
                "not in a problem folder — pass a slug (trailing-zeroes) or a path"
            )
        return d, None

    if os.path.isfile(spec):
        path = os.path.abspath(spec)
        parent = os.path.dirname(path)
        if is_problem_dir(parent):
            return parent, path
        raise CurlError(f"not a problem folder: {parent}")

    if os.path.isdir(spec):
        path = os.path.abspath(spec)
        if is_problem_dir(path):
            return path, None
        walked = problem_from_cwd(path)
        if walked:
            return walked, None

    want = spec.strip().rstrip("/").replace("\\", "/")
    file_hint = None
    for extra in ("sol.py", "sol.cpp", "sol.cc", "sol.cxx"):
        if want == extra or want.endswith("/" + extra):
            file_hint = extra
            want = want[: -len(extra)].rstrip("/")
            break
    if file_hint and not want:
        d = problem_from_cwd()
        if not d:
            raise CurlError(
                "not in a problem folder — pass a slug (trailing-zeroes) or a path"
            )
        src = os.path.join(d, file_hint)
        if not os.path.isfile(src):
            raise CurlError(f"no {file_hint} in {d}")
        return d, src

    matches: list[str] = []
    problems_root = os.path.join(repo_root(), "problems")
    for d in iter_problem_dirs():
        slug = os.path.basename(d)
        rel = os.path.relpath(d, problems_root).replace("\\", "/")
        if want in (slug, rel, rel.split("/", 1)[-1]):
            matches.append(d)
    # unique
    seen: list[str] = []
    for d in matches:
        if d not in seen:
            seen.append(d)
    if len(seen) == 1:
        if file_hint:
            src = os.path.join(seen[0], file_hint)
            if not os.path.isfile(src):
                raise CurlError(f"no {file_hint} in {seen[0]}")
            return seen[0], src
        return seen[0], None
    if len(seen) > 1:
        listing = "\n".join(f"  {os.path.relpath(d, repo_root())}" for d in seen)
        raise CurlError(f"ambiguous {spec!r}:\n{listing}")
    raise CurlError(f"no problem matching {spec!r}")


def unique_dir(category: str, slug: str, taken: Iterable[str]) -> str:
    taken_set = {os.path.abspath(p) for p in taken}
    n = 0
    while True:
        suffix = "" if n == 0 else f"-{n + 1}"
        cand = os.path.join(repo_root(), "problems", category, f"{slug}{suffix}")
        if os.path.abspath(cand) not in taken_set and not os.path.isdir(cand):
            return cand
        n += 1


def problem_dir_for(task: dict[str, str], by_id: dict[str, str]) -> str:
    if task["id"] in by_id:
        return by_id[task["id"]]
    # Reuse a same-named folder even if statement.md has no link yet.
    guessed = os.path.join(repo_root(), "problems", task["category"], task["slug"])
    if os.path.isdir(guessed):
        return guessed
    return unique_dir(task["category"], task["slug"], by_id.values())


def ensure_sol_cpp(out_dir: str) -> None:
    dest = os.path.join(out_dir, "sol.cpp")
    if os.path.exists(dest):
        return
    src = template_cpp()
    os.makedirs(out_dir, exist_ok=True)
    shutil.copy(src, dest)


# ---------------------------------------------------------------------------
# Auth / submit
# ---------------------------------------------------------------------------

def extract_csrf(page: str) -> str | None:
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', page)
    return m.group(1) if m else None


def account_name(page: str) -> str | None:
    m = re.search(r'<a class="account"[^>]*>(.*?)</a>', page, flags=re.S)
    if not m:
        return None
    name = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
    if not name or name.lower() == "login":
        return None
    return name


def whoami(cookie_file: str | None = None) -> str | None:
    cookie_file = cookie_file or cookie_path()
    if not os.path.exists(cookie_file) or os.path.getsize(cookie_file) == 0:
        return None
    try:
        page = fetch(f"{BASE}/problemset/", cookie_file=cookie_file, retries=2)
    except Exception:
        return None
    return account_name(page)


def login(nick: str, password: str, cookie_file: str | None = None) -> str:
    cookie_file = cookie_file or cookie_path()
    # Fresh jar.
    open(cookie_file, "w").close()
    os.chmod(cookie_file, 0o600)
    page = fetch(LOGIN_URL, cookie_file=cookie_file)
    csrf = extract_csrf(page)
    if not csrf:
        raise CurlError("could not find csrf_token on the login page")
    code, final, body = _curl(
        LOGIN_URL,
        data={"csrf_token": csrf, "nick": nick, "pass": password},
        cookie_file=cookie_file,
        referer=LOGIN_URL,
    )
    name = account_name(body) or whoami(cookie_file)
    if not name:
        raise CurlError("login failed — check username/password")
    if code >= 400:
        raise CurlError(f"login HTTP {code} ({final})")
    return name


def task_id_from_problem_dir(prob_dir: str) -> str:
    stmt = os.path.join(prob_dir, "statement.md")
    if os.path.isfile(stmt):
        tid = task_id_from_text(open(stmt, encoding="utf-8", errors="replace").read())
        if tid:
            return tid
    raise CurlError(
        f"no CSES task id in {stmt} — fetch the statement first "
        f"(cses fetch <url> {prob_dir})"
    )


def sol_looks_like_template(sol_path: str) -> bool:
    try:
        src = open(sol_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return False
    tmpl_path = template_for(sol_path)
    tmpl = ""
    if tmpl_path:
        try:
            tmpl = open(tmpl_path, encoding="utf-8", errors="replace").read()
        except OSError:
            tmpl = ""

    def norm(s: str) -> str:
        return re.sub(r"\s+", "", s)

    return bool(tmpl and norm(src) == norm(tmpl))


def pick_source_file(prob_dir: str) -> str:
    """Prefer a real sol.py over an untouched sol.cpp from sync."""
    cpp = os.path.join(prob_dir, "sol.cpp")
    py = os.path.join(prob_dir, "sol.py")
    cpp_ok = os.path.isfile(cpp)
    py_ok = os.path.isfile(py)
    if py_ok and (not cpp_ok or sol_looks_like_template(cpp)):
        return py
    if cpp_ok:
        return cpp
    if py_ok:
        return py
    raise CurlError(f"no sol.cpp or sol.py in {prob_dir}")


def resolve_source(
    prob_dir: str,
    source: str | None = None,
    lang: str | None = None,
    option: str | None = None,
) -> tuple[str, str, str]:
    """Return (source_path, CSES lang, CSES option)."""
    path = os.path.abspath(source) if source else pick_source_file(prob_dir)
    if not os.path.isfile(path):
        raise CurlError(f"no solution file: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in LANG_BY_EXT:
        raise CurlError(f"unsupported solution type: {path}")
    auto_lang, auto_opt = LANG_BY_EXT[ext]
    return path, lang or auto_lang, option or auto_opt


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def parse_result_page(page: str) -> dict[str, str | list[str]]:
    info: dict[str, str | list[str]] = {}
    # CSES uses `<td >` (space before `>`), so allow attributes on the cells.
    for m in re.finditer(r"<tr>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>", page, flags=re.S):
        key = strip_tags(m.group(1)).rstrip(":")
        val = strip_tags(m.group(2))
        if key:
            info[key] = val
    tests: list[str] = []
    times: dict[str, str] = {}
    for m in re.finditer(
        r"<tr>\s*<td[^>]*>\s*(#?\d+)\s*</td>\s*<td[^>]*class=\"[^\"]*verdict[^\"]*\"[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
        page,
        flags=re.S,
    ):
        num = m.group(1).strip()
        if not num.startswith("#"):
            num = "#" + num
        verd = strip_tags(m.group(2))
        t = strip_tags(m.group(3))
        tests.append(f"{num}  {verd}  {t}")
        times[num.lstrip("#")] = t
    if not tests:
        cells = [
            strip_tags(c)
            for c in re.findall(r'class="[^"]*verdict[^"]*"[^>]*>(.*?)</t', page, flags=re.S)
            if strip_tags(c)
        ]
        if cells and cells[0].upper() == "ACCEPTED":
            cells = cells[1:]
        tests = cells
    info["tests"] = tests
    info["test_times"] = times  # type: ignore[assignment]
    info["test_details"] = parse_test_details(page)  # type: ignore[assignment]
    return info


def parse_test_details(page: str) -> list[dict[str, str]]:
    """Per-test input / expected / got / feedback from the result page."""
    chunks = re.split(r'<h4 id="test(\d+)">', page)
    out: list[dict[str, str]] = []
    for i in range(1, len(chunks) - 1, 2):
        num = chunks[i]
        body = chunks[i + 1]
        stop = body.find('<h4 id="test')
        if stop != -1:
            body = body[:stop]
        vm = re.search(r"Verdict:\s*(.*?)(?:</p>|<table)", body, flags=re.S)
        verdict = strip_tags(vm.group(1)) if vm else ""
        fields: dict[str, str] = {}
        for m in re.finditer(
            r"<tr><th>([^<]+)</th></tr>\s*<tr><td><samp>(.*?)</samp>",
            body,
            flags=re.S,
        ):
            key = strip_tags(m.group(1)).lower()
            fields[key] = html.unescape(m.group(2))
        fb = re.search(r"Feedback:\s*(.*?)(?:<br\s*/?>|<h4|$)", body, flags=re.S)
        feedback = html.unescape(re.sub(r"<[^>]+>", "", fb.group(1))).strip() if fb else ""
        out.append(
            {
                "num": num,
                "verdict": verdict,
                "input": fields.get("input", ""),
                "expected": fields.get("correct output", ""),
                "got": fields.get("user output", ""),
                "feedback": feedback,
            }
        )
    return out


LAST_SUBMIT = "last-submit.txt"


def _clip(text: str, max_lines: int = 40, max_chars: int = 2500) -> str:
    text = text.replace("\r\n", "\n")
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n… (truncated)\n"
    lines = text.splitlines()
    if len(lines) > max_lines:
        text = "\n".join(lines[:max_lines]) + "\n… (truncated)\n"
    return text


def _indent(text: str, prefix: str = "    ") -> str:
    text = text.replace("\r\n", "\n").rstrip("\n")
    if not text:
        return prefix + "(empty)"
    return "\n".join(prefix + line for line in text.splitlines())


def _field_lines(label: str, body: str, clip: bool = False) -> list[str]:
    data = _clip(body) if clip else body.replace("\r\n", "\n")
    data = data.rstrip("\n")
    rows = data.splitlines() or [""]
    if len(rows) == 1:
        return [f"  {label:<10} {rows[0]}"]
    return [f"  {label}:"] + [f"    {line}" for line in rows]


def _mark(verdict: str) -> str:
    return "PASS" if (verdict or "").upper() == "ACCEPTED" else "FAIL"


def format_summary_table(info: dict[str, str | list[str]]) -> list[str]:
    details = [d for d in (info.get("test_details") or []) if isinstance(d, dict)]
    times = info.get("test_times") if isinstance(info.get("test_times"), dict) else {}
    rows: list[tuple[str, str, str]] = []
    if details:
        for d in details:
            num = str(d.get("num", ""))
            t = times.get(num, "") if isinstance(times, dict) else ""
            rows.append((num, str(d.get("verdict") or ""), str(t)))
    else:
        for line in info.get("tests") or []:
            m = re.match(r"#(\d+)\s+(.*?)\s+(\d+\.\d+\s*s)\s*$", str(line))
            if m:
                rows.append((m.group(1), m.group(2).strip(), m.group(3)))
            else:
                rows.append(("-", str(line), ""))
    if not rows:
        return []
    w_n = max(2, max(len(n) for n, _, _ in rows))
    w_v = max(len("verdict"), max(len(v) for _, v, _ in rows))
    w_t = max(len("time"), max(len(t) for _, _, t in rows))
    head = f"  {'#':>{w_n}}  {'ok':<4}  {'verdict':<{w_v}}  {'time':<{w_t}}"
    rule = "  " + "-" * (len(head) - 2)
    out = ["Summary", head, rule]
    for num, verd, t in rows:
        out.append(f"  {num:>{w_n}}  {_mark(verd):<4}  {verd:<{w_v}}  {t:<{w_t}}")
    passed = sum(1 for _, v, _ in rows if v.upper() == "ACCEPTED")
    out.append(rule)
    out.append(f"  {passed}/{len(rows)} passed")
    return out


def format_test_card(detail: dict[str, str], time_s: str = "", clip: bool = False) -> list[str]:
    num = detail.get("num", "?")
    verd = detail.get("verdict") or ""
    title = f"Test #{num}  {_mark(verd)}  {verd}"
    if time_s:
        title += f"  {time_s}"
    bar = "=" * max(48, min(64, len(title) + 8))
    lines = [bar, title, bar]
    for key, label in (("input", "input"), ("expected", "expected"), ("got", "got"), ("feedback", "note")):
        val = detail.get(key) or ""
        if val:
            lines.extend(_field_lines(label, val, clip=clip))
    if not any(detail.get(k) for k in ("input", "expected", "got", "feedback")):
        lines.append("  (CSES did not publish this test's input/output)")
    return lines


def first_failed_test(info: dict[str, str | list[str]]) -> dict[str, str] | None:
    for d in info.get("test_details") or []:
        if not isinstance(d, dict):
            continue
        if str(d.get("verdict", "")).upper() != "ACCEPTED":
            return d
    return None


def print_first_failure(info: dict[str, str | list[str]]) -> None:
    fail = first_failed_test(info)
    if not fail:
        return
    num = fail["num"]
    times = info.get("test_times") or {}
    t = times.get(num, "") if isinstance(times, dict) else ""
    print()
    for line in format_test_card(fail, t, clip=True):
        print("  " + line)


def write_submit_report(
    prob_dir: str,
    submit_id: str,
    verdict: str,
    score: str,
    info: dict[str, str | list[str]],
    compiler: str = "",
) -> str:
    path = os.path.join(prob_dir, LAST_SUBMIT)
    times = info.get("test_times") if isinstance(info.get("test_times"), dict) else {}
    details = [d for d in (info.get("test_details") or []) if isinstance(d, dict)]
    lines: list[str] = [
        f"Submission  {submit_id}",
        f"URL         {BASE}/problemset/result/{submit_id}",
        f"Task        {info.get('Task', '')}",
        f"Result      {verdict}" + (f"  ({score})" if score else ""),
        f"Submitted   {info.get('Submission time', '')}",
        f"Language    {info.get('Language', '')}",
        "",
    ]
    table = format_summary_table(info)
    if table:
        lines.extend(table)
        lines.append("")
    if compiler:
        lines.append("Compiler")
        lines.append(_indent(compiler.rstrip()))
        lines.append("")
    failed = [d for d in details if str(d.get("verdict", "")).upper() != "ACCEPTED"]
    passed = [d for d in details if str(d.get("verdict", "")).upper() == "ACCEPTED"]

    def has_io(d: dict[str, str]) -> bool:
        return any(d.get(k) for k in ("input", "expected", "got", "feedback"))

    with_io = [d for d in details if has_io(d)]
    if with_io:
        lines.append(f"Tests with I/O ({len(with_io)})")
        lines.append("")
        for d in with_io:
            t = times.get(d["num"], "") if isinstance(times, dict) else ""
            lines.extend(format_test_card(d, str(t)))
            lines.append("")
    elif failed:
        lines.append(f"Failed tests ({len(failed)})")
        lines.append("")
        for d in failed:
            t = times.get(d["num"], "") if isinstance(times, dict) else ""
            lines.extend(format_test_card(d, str(t)))
            lines.append("")
    quiet_pass = [d for d in passed if not has_io(d)]
    if quiet_pass:
        ids = ", ".join(f"#{d['num']}" for d in quiet_pass)
        lines.append(f"Passed tests ({len(quiet_pass)}): {ids}")
        lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def derive_verdict(info: dict[str, str | list[str]], status: str) -> str:
    result = str(info.get("Result") or "").strip()
    if result:
        # "ACCEPTED" or "WRONG ANSWER" etc. — ignore surrounding noise.
        up = result.upper()
        for label in (
            "ACCEPTED",
            "WRONG ANSWER",
            "TIME LIMIT EXCEEDED",
            "RUNTIME ERROR",
            "MEMORY LIMIT EXCEEDED",
            "OUTPUT LIMIT EXCEEDED",
            "COMPILE ERROR",
            "PARTIAL",
        ):
            if label in up:
                return label
        return result
    tests = [str(t) for t in (info.get("tests") or [])]
    if status == "COMPILE ERROR" or (status or "").startswith("COMPILE"):
        return "COMPILE ERROR"
    if tests:
        labels = []
        for t in tests:
            m = re.search(
                r"(COMPILE ERROR|WRONG ANSWER|TIME LIMIT EXCEEDED|RUNTIME ERROR|MEMORY LIMIT EXCEEDED|OUTPUT LIMIT EXCEEDED|PARTIAL|ACCEPTED)",
                t,
                flags=re.I,
            )
            labels.append((m.group(1).upper() if m else t.split()[1] if len(t.split()) > 1 else t).upper())
        if labels and all(x == "ACCEPTED" for x in labels):
            return "ACCEPTED"
        for x in labels:
            if x != "ACCEPTED":
                return x
    return (status or "UNKNOWN").upper()


def test_score(info: dict[str, str | list[str]]) -> str:
    tests = [str(t) for t in (info.get("tests") or [])]
    if not tests:
        return ""
    ok = sum(1 for t in tests if re.search(r"\bACCEPTED\b", t, flags=re.I))
    return f"{ok}/{len(tests)}"


def record_verdict(prob_dir: str, verdict: str, submit_id: str, info: dict[str, str | list[str]]) -> str:
    """Write/replace a **Verdict:** line in statement.md. Return the line."""
    score = test_score(info)
    when = str(info.get("Submission time") or "").strip()
    url = f"{BASE}/problemset/result/{submit_id}"
    bits = [verdict]
    if score:
        bits.append(score)
    if when:
        bits.append(when)
    bits.append(f"[submission {submit_id}]({url})")
    line = "**Verdict:** " + " · ".join(bits)
    stmt = os.path.join(prob_dir, "statement.md")
    try:
        text = open(stmt, encoding="utf-8", errors="replace").read()
    except OSError:
        return line
    if re.search(r"^\*\*Verdict:\*\*.*$", text, flags=re.M):
        text = re.sub(r"^\*\*Verdict:\*\*.*$", line, text, count=1, flags=re.M)
    else:
        # Insert after Link / Limits header block.
        m = re.search(r"(\*\*Limits:\*\*.*\n)", text)
        if m:
            text = text[: m.end()] + "\n" + line + "\n" + text[m.end() :]
        else:
            m = re.search(r"(\*\*Link:\*\*.*\n)", text)
            if m:
                text = text[: m.end()] + "\n" + line + "\n" + text[m.end() :]
            else:
                text = text.rstrip() + "\n\n" + line + "\n"
    with open(stmt, "w", encoding="utf-8") as f:
        f.write(text)
    return line


def next_unsolved(prob_dir: str | None = None) -> str | None:
    """Next unsolved problem in CSES list order (skips ones already ACCEPTED)."""
    here_id = None
    if prob_dir:
        try:
            here_id = task_id_from_problem_dir(prob_dir)
        except Exception:
            here_id = None
    try:
        tasks = parse_problem_list(fetch(LIST_URL, retries=1))
    except Exception:
        return None
    ids = [t["id"] for t in tasks]
    if here_id and here_id in ids:
        idx = ids.index(here_id)
        order = tasks[idx + 1 :] + tasks[: idx + 1]
    else:
        order = tasks
    by_id = existing_problems()
    for t in order:
        if here_id and t["id"] == here_id:
            continue
        path = by_id.get(t["id"])
        if not path:
            continue
        try:
            with open(os.path.join(path, "statement.md"), encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            text = ""
        if re.search(r"\*\*Verdict:\*\*.*ACCEPTED", text, flags=re.I):
            continue
        return os.path.relpath(path, repo_root())
    return None


def _paint(text: str, ok: bool) -> str:
    if not sys.stdout.isatty():
        return text
    color = "\033[32m" if ok else "\033[31m"
    return f"{color}{text}\033[0m"


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def celebrate(title: str, score: str) -> None:
    from celebrate import play

    play(title, score)


def open_in_editor(path: str) -> None:
    editor = os.environ.get("EDITOR", "").strip()
    candidates: list[list[str]] = []
    for bin_name in ("cursor", "code"):
        if shutil.which(bin_name):
            candidates.append([bin_name, path])
    if editor:
        candidates.append(editor.split() + [path])
    for cmd in candidates:
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  opened  {path}", flush=True)
            return
        except OSError:
            continue
    print(f"  open    {path}", flush=True)


def offer_next(rel_dir: str) -> None:
    hint = f"cses run {os.path.basename(rel_dir)}"
    if not _interactive():
        print(f"  next     {rel_dir}")
        print(f"           {hint}")
        return
    try:
        ans = input(f"Open next problem ({rel_dir})? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if ans in ("", "y", "yes"):
        open_in_editor(os.path.join(repo_root(), rel_dir, "sol.cpp"))
    else:
        print(f"  skipped  {hint}")


def poll_status(submit_id: str, cookie_file: str, timeout: float = 120.0) -> str:
    start = time.time()
    last = ""
    while time.time() - start < timeout:
        code, _, body = _curl(
            f"{STATUS_URL}?entry={urllib.parse.quote(submit_id)}",
            cookie_file=cookie_file,
        )
        status = body.strip()
        if status != last:
            msg = status if status else f"HTTP {code}"
            print(f"  {msg}", flush=True)
            last = status
        if status in {"READY", "COMPILE ERROR"} or status.startswith("COMPILE"):
            return status
        time.sleep(0.6)
    return last or "TIMEOUT"


def submit_solution(
    prob_dir: str,
    *,
    source: str | None = None,
    lang: str | None = None,
    option: str | None = None,
    cookie_file: str | None = None,
) -> int:
    cookie_file = cookie_file or cookie_path()
    prob_dir = os.path.abspath(prob_dir)
    sol, lang, option = resolve_source(prob_dir, source=source, lang=lang, option=option)
    if os.path.getsize(sol) > 128 * 1024:
        raise CurlError("source is over CSES's 128 kB limit")
    if sol_looks_like_template(sol):
        raise CurlError(f"{sol} still looks like the empty template — refusing to submit")

    nick = ensure_session(cookie_file)

    task = task_id_from_problem_dir(prob_dir)
    submit_page_url = f"{BASE}/problemset/submit/{task}/"
    page = fetch(submit_page_url, cookie_file=cookie_file)
    csrf = extract_csrf(page)
    if not csrf:
        # Task page as a fallback.
        page = fetch(f"{BASE}/problemset/task/{task}", cookie_file=cookie_file)
        csrf = extract_csrf(page)
    if not csrf:
        raise CurlError("could not find csrf_token — try: cses login")

    print(f"submitting {sol}", flush=True)
    print(f"  user   {nick}", flush=True)
    print(f"  task   {task}  ({BASE}/problemset/task/{task})", flush=True)
    print(f"  lang   {lang} / {option}", flush=True)

    code, final, body = _curl(
        SEND_URL,
        form=[
            ("csrf_token", csrf),
            ("task", task),
            ("lang", lang),
            ("type", "course"),
            ("target", "problemset"),
            ("option", option),
        ],
        upload=("file", sol),
        cookie_file=cookie_file,
        referer=submit_page_url,
        timeout=60,
    )
    if code >= 400:
        raise CurlError(f"submit HTTP {code}")

    sid = None
    m = re.search(r"get_status\.php\?entry=(\d+)", body) or re.search(
        r"/problemset/result/(\d+)", body + "\n" + final
    )
    if m:
        sid = m.group(1)
    if not sid:
        # Last resort: a bare result link.
        m = re.search(r'href="(/problemset/result/\d+)"', body)
        if m:
            sid = m.group(1).rsplit("/", 1)[-1]
    if not sid:
        raise CurlError("submitted, but could not find the result id in CSES's response")

    print(f"  id     {sid}", flush=True)
    print(f"  poll   {BASE}/problemset/result/{sid}", flush=True)
    status = poll_status(sid, cookie_file)
    result_page = fetch(f"{BASE}/problemset/result/{sid}", cookie_file=cookie_file)
    info = parse_result_page(result_page)
    verdict = derive_verdict(info, status)
    score = test_score(info)
    ok = verdict == "ACCEPTED"

    print()
    for key in ("Task", "Sender", "Submission time", "Language", "Status", "Result"):
        if key in info and not isinstance(info[key], list):
            print(f"  {key + ':':<18} {info[key]}")
    tests = info.get("tests") or []
    if tests:
        print("  tests:")
        for line in tests:  # type: ignore[assignment]
            print(f"    {line}")
    compiler = ""
    if verdict == "COMPILE ERROR":
        pre = re.findall(r"<pre>(.*?)</pre>", result_page, flags=re.S)
        if pre:
            compiler = html.unescape(re.sub(r"<[^>]+>", "", pre[0]))
            print("  compiler:")
            print(compiler[:2000])

    if ok:
        celebrate(str(info.get("Task") or ""), score)
    else:
        banner = verdict if not score else f"{verdict}  ({score})"
        print()
        print(_paint(banner, False), flush=True)
        table = format_summary_table(info)
        if table:
            print()
            for line in table:
                print(line)
        print_first_failure(info)

    saved = record_verdict(prob_dir, verdict, sid, info)
    report = write_submit_report(prob_dir, sid, verdict, score, info, compiler=compiler)
    rel = os.path.relpath(os.path.join(prob_dir, "statement.md"), repo_root())
    rel_report = os.path.relpath(report, repo_root())
    print(f"\n  recorded {saved}")
    print(f"  in       {rel}")
    print(f"  report   {rel_report}")
    print(f"  result   {BASE}/problemset/result/{sid}")
    nxt = next_unsolved(prob_dir) if ok else None
    if nxt:
        offer_next(nxt)
    return 0 if ok else 1
