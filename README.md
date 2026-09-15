# CSES kit

Unofficial CLI to fetch [CSES](https://cses.fi/problemset/) statements, test a
solution locally, and submit from the terminal. Not affiliated with CSES, and
not the University of Helsinki [cses-cli](https://github.com/csesfi/cses-cli).

Repo: [yatharthsol090/cses-kit](https://github.com/yatharthsol090/cses-kit).

C++17 is the default (`sol.cpp` from `template.cpp`). Python 3 works if you add
`sol.py` (copy `template.py`), and Node.js works with `sol.js` (copy `template.js`).
Folder run/submit keeps a real C++ solution as the default, otherwise prefers
Python and then Node.js. Pass a `.py` or `.js` path to force that source.

Problem statements belong to CSES and are **not** in this repo. After cloning:

```bash
cses sync
```

## Setup

macOS or Linux with `g++`, `python3`, and `curl`. Node.js is required only for `sol.js` solutions.

```bash
chmod +x cses scripts/run.sh
cp .env.example .env          # only needed to submit
./cses install                # symlink ~/.local/bin/cses
```

`./cses install` cannot change the **current** terminal. Either open a new
tab, or run:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Put that `export` in `~/.zshrc` so it sticks. Until `cses` is on `PATH`, use
`./cses` from the repo root.

### Auth

Prefer a browser session cookie (no password is stored):

1. Log into https://cses.fi in your browser.
2. Open DevTools -> Application -> Cookies -> `https://cses.fi`, copy `PHPSESSID`.
3. `cses login --session <PHPSESSID>` (or set `CSES_PHPSESSID` in `.env`).
4. `cses logout` clears the stored jar.

`CSES_NICK` / `CSES_PASS` password auto-login is deprecated and only used
when `CSES_ALLOW_PASSWORD_LOGIN=1`.

On macOS, `include/bits/stdc++.h` is a shim so `#include <bits/stdc++.h>` works
with Apple clang.

## Commands

```bash
cses sync                              # all public tasks â†’ problems/
cses sync --category introductory      # one section
cses new introductory missing-number https://cses.fi/problemset/task/1083
cses fetch <url> <problem-dir>         # refresh one statement + samples

cses run trailing-zeroes               # sample tests (C++, Python, or Node.js)
cses run trailing-zeroes/sol.py        # force Python
cses run trailing-zeroes/sol.js        # force Node.js
cses run -i                            # in a problem folder; type input

cses submit trailing-zeroes
cses submit trailing-zeroes/sol.py
cses submit trailing-zeroes/sol.js

cses login
cses whoami
cses install
cses celebrate                         # preview the ACCEPTED banner
cses status                            # solved vs remaining per category
cses status --unsolved                 # also list unsolved problem slugs
cses status --category introductory    # filter by category
cses version                           # or: cses --version
```

Slugs, `problems/<cat>/<slug>`, or a `sol.cpp` / `sol.py` / `sol.js` path all work. From
inside a problem folder, omit the name: `cses run` / `cses submit`.

If multiple solution files exist and C++ is a real solution (not the
template), the folder commands use C++. Otherwise they prefer Python, then
Node.js. Pass `sol.py` or `sol.js` to force one explicitly.

## After submit

- Verdict is written into `statement.md`.
- `last-submit.txt` gets a summary table plus any test I/O CSES published.
- On failure, the terminal prints the summary and the first failing test
  (input / expected / got / note).
- On **ACCEPTED**, a short banner plays (`CSES_NO_ANIM=1` to skip). You may be
  offered the next unsolved problem.

Local `cses run` failures use the same card layout. Samples are the public
examples only; hidden tests appear after submit, and only if CSES shows them.

In VS Code / Cursor, open `sol.cpp`, `sol.py`, or `sol.js` and press **Cmd+Shift+B**, or
**Run Task â†’ CSES: submit current problem**.

## Testing notes

- C++: `-std=gnu++17 -O2` plus AddressSanitizer and UBSan.
- Output compare ignores trailing whitespace, like CSES.
- Sanitizer timings are slower than a real submission.

## Version

`cses --version` prints the current [SemVer](https://semver.org/) from the
`VERSION` file. Release notes live in
[CHANGELOG.md](CHANGELOG.md); people with merged work are listed in
[CONTRIBUTORS.md](CONTRIBUTORS.md). GitHub Releases are created from `v*.*.*`
tags — see [CONTRIBUTING.md](CONTRIBUTING.md#versioning-and-releases).

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and
the [Code of Conduct](CODE_OF_CONDUCT.md).

Look at [open issues](https://github.com/yatharthsol090/cses-kit/issues) first
(especially `good first issue`). Setup is the same as above: clone, `chmod +x
cses scripts/run.sh`, then `./cses` from the repo root.

Run tests from the repo root:

```bash
python3 -m unittest discover -s tests -v
```

Behavior changes should include matching tests in `tests/`. Keep `.env`,
`.cses/`, and `problems/` out of git. Prefer stdlib + `curl`. Leave the 0.2s
delay (or gentler) on bulk fetches.

## License

MIT for this tooling. CSES content remains Â© its authors; fetch it yourself.

