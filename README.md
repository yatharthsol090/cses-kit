# CSES kit

Unofficial CLI to fetch [CSES](https://cses.fi/problemset/) statements, test a
solution locally, and submit from the terminal. Not affiliated with CSES, and
not the University of Helsinki [cses-cli](https://github.com/csesfi/cses-cli).

Repo: [yatharthsol090/cses-kit](https://github.com/yatharthsol090/cses-kit).

C++17 is the default (`sol.cpp` from `template.cpp`). Python 3 works if you add
`sol.py` (copy `template.py`). Run/submit pick Python when `sol.cpp` is missing
or still the empty template, or when you pass the `.py` path. CSES gets
`Python3` / `PyPy3` (`--option CPython3` to override).

Problem statements belong to CSES and are **not** in this repo. After cloning:

```bash
cses sync
```

## Setup

macOS or Linux with `g++`, `python3`, and `curl`.

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

On macOS, `include/bits/stdc++.h` is a shim so `#include <bits/stdc++.h>` works
with Apple clang.

## Commands

```bash
cses sync                              # all public tasks → problems/
cses sync --category introductory      # one section
cses new introductory missing-number https://cses.fi/problemset/task/1083
cses fetch <url> <problem-dir>         # refresh one statement + samples

cses run trailing-zeroes               # sample tests (C++ or Python)
cses run trailing-zeroes/sol.py        # force Python
cses run -i                            # in a problem folder; type input

cses submit trailing-zeroes
cses submit trailing-zeroes/sol.py

cses next                              # open next unsolved problem
cses next trailing-zeroes              # open next unsolved after this problem

cses login
cses whoami
cses install
cses celebrate                         # preview the ACCEPTED banner
```

Slugs, `problems/<cat>/<slug>`, or a `sol.cpp` / `sol.py` path all work. From
inside a problem folder, omit the name: `cses run` / `cses submit`.

If both `sol.cpp` and `sol.py` exist and C++ is a real solution (not the
template), the folder commands use C++. Pass `sol.py` to force Python.

## After submit

- Verdict is written into `statement.md`.
- `last-submit.txt` gets a summary table plus any test I/O CSES published.
- On failure, the terminal prints the summary and the first failing test
  (input / expected / got / note).
- On **ACCEPTED**, a short banner plays (`CSES_NO_ANIM=1` to skip). You may be
  offered the next unsolved problem.

Local `cses run` failures use the same card layout. Samples are the public
examples only; hidden tests appear after submit, and only if CSES shows them.

In VS Code / Cursor, open `sol.cpp` or `sol.py` and press **Cmd+Shift+B**, or
**Run Task → CSES: submit current problem**.

## Testing notes

- C++: `-std=gnu++17 -O2` plus AddressSanitizer and UBSan.
- Output compare ignores trailing whitespace, like CSES.
- Sanitizer timings are slower than a real submission.

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
