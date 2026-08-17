# Development Guide

> If you are a coding agent, please read [AGENTS.md](AGENTS.md) instead.

This document is for human contributors. It covers how to set up a development environment, the branch workflow, and what to do before opening a PR.

---

## Prerequisites

- **Binary Ninja** (build 3164 or newer) and/or **IDA Pro 9.x**
- **Python 3.10–3.11** recommended (see note below on IDA Pro + Python versions)
- **Git**
- An API key for at least one supported LLM provider (Anthropic, OpenAI, Google, or a local Ollama instance)

> **IDA Pro note:** Python 3.10 is the safest choice. Higher versions may trigger a Shiboken UAF crash during Qt signal dispatch. See the IDA API Notes section of AGENTS.md for details.

---

## Installation (Development)

Clone the repo and symlink it into the host's plugin directory so changes take effect on the next launch without reinstalling.

**Binary Ninja**
```bash
# macOS
git clone https://github.com/alicangnll/Spectra
ln -s "$(pwd)/spectra" ~/Library/Application\ Support/Binary\ Ninja/plugins/spectra

# Linux
git clone https://github.com/alicangnll/Spectra
ln -s "$(pwd)/spectra" ~/.binaryninja/plugins/spectra

# Windows (run as Administrator)
git clone https://github.com/alicangnll/Spectra
mklink /D "%APPDATA%\Binary Ninja\plugins\spectra" "<full path to cloned repo>"
```

**IDA Pro**
```bash
# macOS / Linux
ln -s "$(pwd)/spectra" ~/.idapro/plugins/spectra

# Windows
mklink /D "%APPDATA%\Hex-Rays\IDA Pro\plugins\spectra" "<full path to cloned repo>"
```

---

## Python Dependencies

Install the runtime dependencies into the Python environment used by your host:

```bash
pip install anthropic>=0.39.0 openai>=1.50.0 google-genai>=1.0.0 tomli>=2.0.0
```

For development tooling (CI checks, running tests locally):

```bash
pip install ruff mypy pytest desloppify
```

---

## Branch Workflow

```
feat/my-thing  ─┐
fix/some-bug   ─┤──► dev ──► main
chore/deps     ─┘
```

1. Branch off `dev` using a descriptive prefix:
   - `feat/` — new feature
   - `fix/` — bug fix
   - `refactor/` — code restructure, no behavior change
   - `chore/` — deps, tooling, docs
2. Make your changes in small, focused commits
3. Run the local CI script (see below) before pushing
4. Open a PR targeting `dev`
5. Once reviewed and CI passes (run `./ci-local.sh`; the Actions workflow is manual-only), it gets merged to `dev`
6. Releases go from `dev` → `main` with a version tag

**Direct pushes to `main` are not allowed** — must go through a PR. `dev` accepts direct pushes.

---

## Before Pushing — Local CI Check

Run this script after every feature or fix, before opening a PR:

```bash
./ci-local.sh
```

This mirrors exactly what the GitHub Actions workflow runs. It will catch formatting errors, lint issues, type errors, test failures, and code quality regressions.

**GitHub Actions CI is manual-only** — it does *not* run on push or PR.
This script is the primary gate for every commit. Run the remote workflow
when you want it: **Actions → CI → "Run workflow"**, or:

```bash
gh workflow run ci.yml
```

If ruff reports formatting issues, auto-fix them:

```bash
./ci-local.sh --fix
```

The script installs `ruff` and `mypy` if they are not already available. It skips steps whose tools are missing rather than failing hard, so it is safe to run in a partial environment.

---

## Running Tests

```bash
python3 -m pytest tests/ -v
```

Tests are organized under `tests/` by subsystem:

```
tests/
├── agent/       # Agent loop, plan mode, exploration, session
├── core/        # Config, sanitize, errors, profile, logging
│                # + xref, function_naming, type_recovery, bookmark, advanced_search (v1.2.5+)
├── providers/   # All LLM providers
├── tools/       # Tool implementations (binja, IDA, shared)
└── mocks/       # ida_mock — stubs the IDA Pro API for testing outside IDA
```

Binary Ninja and IDA Pro APIs are stubbed at test time — you do not need either host installed to run the test suite.

### Test-suite gotchas (learned the hard way)

- **Shared IDA mocks are re-installed by several test modules at import
  time** — the last `install_ida_mocks()` call wins in `sys.modules`. A
  module imported earlier still holds the *old* mock objects. If your test
  configures `sys.modules["idautils"]` directly, it may patch a mock the
  module under test never uses (symptom: passes standalone, fails in the
  full suite). Either configure the module's own bindings
  (`spectra_module.idautils`) or `importlib.reload()` it in `setUpModule`
  (see `tests/tools/test_ssl_pinning.py`).
- **`spectra.core.config` is stubbed by some tests** with `MagicMock`s.
  Anything asserting real config save/load behavior must run in a
  **subprocess** (`[sys.executable, "-c", script, repo_root]`) — see
  `TestConfigRoundTrip` in `tests/tools/test_adb.py`. Safety helpers also
  fail closed with `val is True` so a mocked config can never enable the
  unsafe-command bypass.
- **`Signal` vs `QTimer.singleShot` across bindings**: `QTimer.singleShot`
  scheduled from a plain Python worker thread never fires (no event loop).
  Worker→UI communication must use `Signal(...).emit` (queued connection),
  which works identically in PySide6, PyQt5, and PyQt6.

---

## Code Quality

This project uses [desloppify](https://github.com/peteromallet/desloppify) to track codebase health. The current objective score is **89.0/100** (target: 95).

### Recent Improvements (v1.2.5+)

**Tool Parameter Validation:**
- Added automatic validation of required parameters before tool execution
- Clear error messages for missing parameters instead of cryptic TypeErrors
- Implemented in `spectra/tools/registry.py`

**Windows Automatic Installation:**
- Added automatic `anthropic` package installation for Windows users
- Fallback to system Python when IDA's Python is not found
- Implemented in `spectra_plugin.py`

Run a scan locally at any time:

```bash
desloppify scan
desloppify status   # score dashboard
desloppify issues   # work queue of findings
```

The `desloppify review` command (subjective scoring) uses an LLM and is run manually before releases, not on every change.

**Python version note:** desloppify's AST-based detectors are sensitive to the Python version running the scan. GitHub Actions uses Python 3.11 (~89.4 score). Different local versions will yield slightly different scores — the 0.5-point baseline gap is intentional to absorb this variance. For consistent local results, install `uv`; the `.python-version` file in the repo root pins to 3.11 and `ci-local.sh` will use it automatically.

```bash
pip install uv                   # install uv once
uv add desloppify --dev          # add desloppify (ci-local.sh does this automatically)
```

---

## Commit Style

```
feat(agent): add streaming cancellation for plan mode
fix(binja): handle missing function at cursor gracefully
refactor(providers): extract retry logic into base class
security: strip homoglyph sequences in sanitize.py
docs: update tool registration guide in AGENTS.md
```

Format: `type(scope): short description`
- One logical change per commit
- Scope is the subsystem: `agent`, `binja`, `ida`, `ui`, `providers`, `mcp`, `skills`, `core`

---

## Release Process

1. Merge `dev` → `main` via PR
2. Bump `version` in `plugin.json`
3. Tag and push:
   ```bash
   git tag v0.x.x
   git push origin v0.x.x
   ```
4. GitHub Actions validates the tag matches `plugin.json` and publishes the GitHub Release
5. Binary Ninja plugin manager picks up the new version from `main` automatically

---

## Getting Help

- Read [AGENTS.md](AGENTS.md) for deep technical documentation on internals, architecture decisions, and coding rules
- Open an issue at https://github.com/alicangnll/Spectra/issues
