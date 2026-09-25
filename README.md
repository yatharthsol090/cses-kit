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

macOS or Linux with `g++`, `python3`, and `curl`. Node.js is required only for
`sol.js` solutions.

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

`.env` (gitignored):

```
CSES_NICK=your_username
CSES_PASS=your_password
```

For the complete interactive setup, run `cses setup`. It asks for the login
details, editor (`nvim`, `vim`, `code`, `cursor`, or a custom command), existing
problems directory, and starting roadmap.

On macOS, `include/bits/stdc++.h` is a shim so `#include <bits/stdc++.h>` works
with Apple clang.

## Roadmap and release notes

A roadmap is an ordered, user-provided list of tasks. A text roadmap uses one
task ID, CSES task URL, or slug per line; comments and blank lines are allowed.
Unknown lines are errors and the file order is preserved.

Release notes are the changelog for the project itself, not the problem set. They live in [CHANGELOG.md](CHANGELOG.md) and summarize new features, fixes, and compatibility changes for the app.


## Commands

```bash
cses sync                              # all public tasks → problems/
cses sync --list roadmap.txt           # sync an ordered roadmap
cses sync --category introductory      # one section
cses new introductory missing-number https://cses.fi/problemset/task/1083
cses fetch <url> <problem-dir>         # refresh one statement + samples

cses run trailing-zeroes               # sample tests (C++, Python, or Node.js)
cses run trailing-zeroes/sol.py        # force Python
cses run trailing-zeroes/sol.js        # force Node.js
cses run --timeout 2 trailing-zeroes    # limit each sample to 2 seconds
cses run -i                            # in a problem folder; type input

cses submit trailing-zeroes
cses submit trailing-zeroes/sol.py
cses submit trailing-zeroes/sol.js

cses next                              # open next unsolved problem
cses next trailing-zeroes              # open next unsolved after this problem

cses login
cses whoami
cses install
cses celebrate                         # preview the ACCEPTED banner
cses status                            # solved vs remaining per category
cses status --unsolved                 # also list unsolved problem slugs
cses status --category introductory    # filter by category
cses status --list roadmap.txt         # status in roadmap order
cses run --list roadmap.txt             # run each downloaded roadmap entry
cses version                           # or: cses --version
cses tui                               # browse the selected roadmap
```

The TUI reads the configured roadmap without modifying it. Downloaded and
solved state is derived from local problem folders and the `Verdict:` line in
each `statement.md`.

Slugs, `problems/<cat>/<slug>`, or a `sol.cpp` / `sol.py` / `sol.js` path all work. From
inside a problem folder, omit the name: `cses run` / `cses submit`.

`--timeout` applies to sample tests only; it does not affect `cses run -i` or
the no-sample-tests path.

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
**Run Task → CSES: submit current problem**.

## Testing notes

- C++: `-std=gnu++17 -O2` plus AddressSanitizer and UBSan.
- Output compare ignores trailing whitespace, like CSES.
- Sanitizer timings are slower than a real submission.
- `--timeout` is a local safety timer, not a simulation of CSES judge time.

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

MIT for this tooling. CSES content remains © its authors; fetch it yourself.
