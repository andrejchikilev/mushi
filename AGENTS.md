# AGENTS.md

## Project State
- Mushi is intended to be a persistent task/session manager for coding agents with interchangeable Cursor CLI and OpenCode backends; this is stated in `README.md` but not implemented in tracked source yet.
- The repo now has a Python package manifest and basic pytest config, but no lint/typecheck config, CI workflow, or task runner yet. Do not invent commands such as `ruff` or `mypy` until executable config is added.
- Current implementation: domain schemas (Phase 1), filesystem storage (Phase 2), task/session/profile workflows with CLI (Phase 3), backend adapter protocol with Cursor CLI and OpenCode adapters and CLI integration (Phase 4), handoff generation and session resume (Phase 5), search (Phase 6), MVP hardening with error handling and migration placeholder (Phase 7).

## Tooling
- Use `uv` for Python dependency management, environment setup, running project commands, and lockfile updates. Do not introduce `pip`, direct `python` runner conventions, Poetry, Pipenv, or ad-hoc virtualenv workflows unless the repo explicitly changes direction.
- Install/sync dependencies with `uv sync`.
- Run tests with `uv run pytest`.
- Run the CLI with `uv run mushi --help` or `uv run mushi --version`.
- Dev mode uses `.mushi/` storage root via `.env` (auto-loaded by CLI). For a system-wide install, `uv tool install --reinstall .` uses XDG default (`~/.local/share/mushi/`).
- When adding a new variable to `.env`, add the same variable to `.env.default` with a placeholder or safe default. `.env.default` is tracked and must never contain secrets (tokens, usernames, passwords, etc.).

## OpenCode Local Files
- `.opencode/` is repo-local OpenCode support, not the application package. Its `package.json` only installs `@opencode-ai/plugin` and `.opencode/.gitignore` ignores those files, so avoid treating `.opencode/node_modules` as project source.

## Phase Execution Order

Each phase (and each subphase within a phase) follows this strict sequence:

1. **Implement** — write the code for the current (sub)phase.
2. **Test** — run `uv run pytest` and fix any failures before proceeding.
3. **Review** — inspect all changes: correctness, edge cases, regressions, schema compat, coverage gaps.
4. **Fix issues** — if the review found problems, fix them.
5. **Repeat step 3** — re-review the fixed code. Maximum **2 review cycles total** per subphase. If after 2 reviews issues remain, stop and wait for instructions.
6. **Document** — if everything is clean, create `.mushi/manual-test-<phase>.md` with concrete shell commands for manual verification of that phase's changes. If not clean, do not create the guide and wait for instructions.
   - The guide must be self-contained: `uv sync`, `export MUSHI_STORAGE_ROOT=.mushi`, exact commands, expected output, and cleanup (`rm -rf .mushi`).
   - This ensures every phase is independently smoke-testable and the knowledge is not lost.

## Verification
- For code changes, run `uv run pytest`.
- Inspect `git status --short` before summarizing changes.
