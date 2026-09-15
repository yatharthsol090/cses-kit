# Contributing

Thanks for helping with this unofficial CSES toolkit. Please be polite to CSES
(keep the sync delay) and never commit `.env`, `.cses/`, or `problems/`.

## Prerequisites

macOS or Linux with `g++`, `python3`, and `curl`. No pip packages.

```bash
git clone https://github.com/YOUR_USER/cses-kit.git
cd cses-kit
chmod +x cses scripts/run.sh
cp .env.example .env   # only if you will submit
```

Until `cses` is on your `PATH`, run `./cses` from the repo root.

## How to run the project

```bash
./cses sync --category introductory
./cses run trailing-zeroes
./cses submit trailing-zeroes
```

See the README for Python (`sol.py`), login, and install.

## How to run tests

From the repo root (stdlib `unittest` only):

```bash
python3 -m unittest discover -s tests -v
```

CI runs the same command. Add or update tests when you change behavior.

## Workflow

1. **Fork** the repository on GitHub.
2. **Clone** your fork.
3. **Branch** from `main`: `git checkout -b feat/short-name`.
4. **Change** only what the issue/PR needs.
5. **Tests:** run the command above; extend `tests/` for new behavior.
6. **PR** against `main`. Fill in the PR template.

Prefer stdlib + `curl`. If you need a new dependency, explain why in the PR.

## Pull requests

- Tests added or updated when behavior changes.
- `python3 -m unittest discover -s tests -v` passes.
- README / CONTRIBUTING updated if the CLI or setup changed.
- User-facing changes listed under `[Unreleased]` in `CHANGELOG.md`.
- No unrelated files, secrets, or CSES problem statements.

## Versioning and releases

cses-kit uses [Semantic Versioning](https://semver.org/). The number in
`VERSION` is what `cses --version` prints.

| Bump | Tag examples | When |
| --- | --- | --- |
| **PATCH** | `v0.2.1` | Bug fix; no new command or language |
| **MINOR** | `v0.2.0`, `v0.3.0` | New command, language, or user-facing behavior |
| **MAJOR** | `v1.0.0`, `v2.0.0` | Breaking CLI change, or declaring the CLI stable |

`0.x` means the command surface may still move. `v1.0.0` is when we call it
stable.

### Cutting a release (maintainers)

1. On `main`, set `VERSION` to `X.Y.Z`.
2. In `CHANGELOG.md`, move `[Unreleased]` notes under
   `## [X.Y.Z] - YYYY-MM-DD` and add compare links for the new tag.
3. Add first-time merged authors to `CONTRIBUTORS.md` if they are not listed.
4. Commit and push `main` (linear history; squash-merge PRs as usual).
5. Tag annotated and push the tag (not before `VERSION` matches):

```bash
git tag -a vX.Y.Z -m vX.Y.Z
git push origin vX.Y.Z
```

Pushing `vX.Y.Z` runs `.github/workflows/release.yml`, which checks `VERSION`
and publishes a [GitHub Release](https://github.com/yatharthsol090/cses-kit/releases)
from that changelog section.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
