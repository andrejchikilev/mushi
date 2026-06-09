# AGENTS.md

## Project State
- Mushi is intended to be a persistent task/session manager for coding agents with interchangeable Cursor CLI and OpenCode backends; this is stated in `README.md` but not implemented in tracked source yet.
- The repo now has a Python package manifest and basic pytest config, but no lint/typecheck config, CI workflow, or task runner yet. Do not invent commands such as `ruff` or `mypy` until executable config is added.
- Current implementation is Phase 1 only: domain schemas, a minimal Typer CLI, package boundaries, and tests. There are no backend implementations or filesystem storage implementation yet.

## Tooling
- Use `uv` for Python dependency management, environment setup, running project commands, and lockfile updates. Do not introduce `pip`, direct `python` runner conventions, Poetry, Pipenv, or ad-hoc virtualenv workflows unless the repo explicitly changes direction.
- Install/sync dependencies with `uv sync`.
- Run tests with `uv run pytest`.
- Run the CLI with `uv run mushi --help` or `uv run mushi --version`.

## OpenCode Local Files
- `.opencode/` is repo-local OpenCode support, not the application package. Its `package.json` only installs `@opencode-ai/plugin` and `.opencode/.gitignore` ignores those files, so avoid treating `.opencode/node_modules` as project source.

## Manual Testing
- After completing each phase (or subphase), create `.mushi-dev/manual-test-<phase>.md` with concrete shell commands for manual verification of that phase's changes.
- The guide must be self-contained: `uv sync`, `export MUSHI_STORAGE_ROOT=.mushi-dev`, exact commands, expected output, and cleanup (`rm -rf .mushi-dev`).
- This ensures every phase is independently smoke-testable and the knowledge is not lost.

## Verification
- For code changes, run `uv run pytest`.
- Inspect `git status --short` before summarizing changes.
