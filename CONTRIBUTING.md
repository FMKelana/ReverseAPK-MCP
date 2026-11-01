# Contributing to ReverseAPK

Thanks for helping improve ReverseAPK. This document covers the development setup, the
conventions used by the project, and the pull request checklist.

By participating you agree to keep the project usable for lawful security research only, as
described in [LEGAL.md](LEGAL.md).

---

## Development setup

```powershell
git clone https://github.com/FMKelana/ReverseAPK-MCP.git
cd ReverseAPK-MCP

python -m venv mcp-server\.venv
mcp-server\.venv\Scripts\python.exe -m pip install -q --upgrade pip
mcp-server\.venv\Scripts\python.exe -m pip install -q -e "mcp-server[dev]"

mcp-server\.venv\Scripts\python.exe -m pytest mcp-server\tests -q
mcp-server\.venv\Scripts\python.exe mcp-server\scripts\smoke_server.py
```

The test suite is self-contained. Toolchain binaries under `tools/` are only needed for
end-to-end runs and are downloaded by `scripts/setup-toolchain.ps1` and
`scripts/setup-android-tools.ps1`.

---

## Repository layout

| Path | Purpose |
|---|---|
| `mcp-server/src/reverseapk_mcp/server.py` | Server entry point and stdio transport |
| `mcp-server/src/reverseapk_mcp/config.py` | Settings, path allow-listing, toolchain resolution |
| `mcp-server/src/reverseapk_mcp/adapters/` | One module per external CLI tool |
| `mcp-server/src/reverseapk_mcp/tools/` | MCP tool registration grouped by domain |
| `mcp-server/src/reverseapk_mcp/indexer/` | SQLite FTS5 code index |
| `mcp-server/tests/` | Unit and integration tests |
| `docs/` | Tool reference, workflow, troubleshooting |

---

## Coding conventions

- Target Python 3.10+ and keep `from __future__ import annotations` in new modules.
- Use type hints for public functions and dataclasses for structured data.
- Never build a shell command string. Use `asyncio.create_subprocess_exec` with an argument
  list, as the existing adapters do.
- Validate every filesystem path with the helpers in `config.py`
  (`ensure_within`, `Settings.session_dir`) before touching the disk.
- Keep tool responses inside the standard JSON envelope (`status`, `summary`, `artifacts`,
  `stats`, `next_steps`, `log_tail`, `data`, `error`).
- Do not write secrets, keystore passwords, or full command lines containing passwords to logs
  or manifests.
- Prefer extending an existing adapter or tool group over adding a new top-level module.
- Documentation under `docs/` is currently written in Indonesian. Keep the existing language
  for consistency, or provide an English translation as a separate file.

---

## Adding a new tool

1. Add or extend an adapter in `mcp-server/src/reverseapk_mcp/adapters/`.
2. Register the tool in the matching module under `mcp-server/src/reverseapk_mcp/tools/`.
3. Document it in `docs/TOOLS.md` (parameters and behavior).
4. Add a test in `mcp-server/tests/`, using temporary directories and fake CLI scripts where
   possible so the test does not require the real toolchain.
5. Run `pytest` and `smoke_server.py` before opening the pull request.

---

## Commit and pull request checklist

- One logical change per pull request, with a short imperative subject line.
- `pytest mcp-server\tests -q` passes locally.
- No generated artifacts (`workspaces/`, `tools/`, `samples/*.apk`, `*.idsig`) are staged.
- No secrets, keystores, `.env` files, or `config/toolchain.json` are staged.
- No absolute personal paths (`C:/Users/...`, a developer's drive letters) or personal email
  addresses are added to source, docs, or configuration examples. Use `<REPO_ROOT>` or
  `%REVERSEAPK_HOME%` placeholders instead.
- New behavior is documented and, when user visible, listed in `README.md`.

---

## Reporting bugs

Include:

- Windows version, Python version, and JDK version.
- The tool name and parameters from the failed call.
- Relevant `log_tail` output with any secrets removed.
- Whether the issue reproduces with the generated `samples/demo.apk`.

Security issues should follow [SECURITY.md](SECURITY.md) instead of the public issue tracker.
