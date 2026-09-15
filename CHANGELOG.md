# Changelog

All notable changes to [cses-kit](https://github.com/yatharthsol090/cses-kit)
are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **MAJOR** (`v1.0.0`, `v2.0.0`, …) — breaking CLI or workflow changes
- **MINOR** (`v0.2.0`, `v0.3.0`, …) — new commands, languages, or user-facing features
- **PATCH** (`v0.2.1`, …) — bug fixes and small internal fixes

While the project is `0.x`, the CLI may still change; `v1.0.0` is when we call
the command surface stable.

## [Unreleased]

### Added
- `cses login --session PHPSESSID` to import a browser session cookie (no password stored).
- `cses logout` to clear the stored cookie jar.
- `CSES_PHPSESSID` environment variable support.

### Changed
- Session cookie is now the documented default auth method.
- `ensure_session` tries the cookie jar first, then `CSES_PHPSESSID`, then (opt-in) password login.

### Deprecated
- `CSES_NICK` / `CSES_PASS` password auto-login is now gated behind `CSES_ALLOW_PASSWORD_LOGIN`.


### Added

- `cses status` — solved vs remaining per category (`--unsolved`, `--category`, `--json`) ([#10](https://github.com/yatharthsol090/cses-kit/pull/10))

## [0.1.0] - 2026-09-15

First tagged release.

### Added

- CLI (`./cses` / `cses`): `sync`, `fetch`, `new`, `run`, `submit`, `login`,
  `whoami`, `install`, `celebrate`, `version`
- C++17 as the default language (`sol.cpp` from `template.cpp`)
- Python 3 (`sol.py`) and Node.js (`sol.js`) run/submit
- Local sample tests via `scripts/run.sh` (g++ / python3 / node)
- CSES login (`.env` + gitignored `.cses/cookies.txt`) and submit with verdict
  polling
- ACCEPTED banner (`celebrate`) and optional next-problem prompt
- Full-file template detection (a real `sol.cpp` that kept the placeholder
  comment is not treated as empty)
- Portable sample timings (`perf_counter()`, no `bc` / `date +%s.%N`)
- Stdlib `unittest` suite and GitHub Actions CI
- SemVer (`VERSION`, `cses version` / `cses --version`), changelog, and GitHub
  Releases from `v*.*.*` tags

### Contributors

See [CONTRIBUTORS.md](CONTRIBUTORS.md).

[Unreleased]: https://github.com/yatharthsol090/cses-kit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yatharthsol090/cses-kit/releases/tag/v0.1.0
