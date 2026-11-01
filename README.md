# ReverseAPK

A typed [Model Context Protocol](https://modelcontextprotocol.io/) server that gives AI agents
(Roo Code, Claude Desktop, or any MCP client) a safe, token-efficient toolkit for Android APK
reverse engineering on **native Windows 10/11 — no Docker required**.

ReverseAPK wraps `apktool`, `jadx`, `aapt2`, `apksigner`, `zipalign`, `adb`, `dexdump`,
`frida`, and `ghidra` behind 35 typed tools. Every action is recorded in a session manifest,
runs with a timeout, and is confined to an allow-listed workspace.

> **Use only on APKs you own or are explicitly authorized to analyze.** See [LEGAL.md](LEGAL.md).

---

## Features

- **35 typed MCP tools** for inventory, decoding, indexing, searching, rebuilding, signing,
  runtime testing, and reconstruction planning.
- **Session isolation** — each analysis lives in `workspaces/<session_id>/` with a
  `manifest.json` that records inputs, hashes, tool versions, artifacts, and step history.
- **Token-efficient code intelligence** — a SQLite FTS5 index powers `code_search`,
  `code_read`, and `callgraph` with pagination instead of dumping entire decompiled trees.
- **Safe process execution** — no `shell=True`, no raw command strings, path allow-listing,
  per-job timeouts, and truncated output tails.
- **Agent UX** — a ready-to-use Roo Code custom mode (`apk-reverse`) with SOP rules and three
  slash commands (`/apk-analyze`, `/apk-rebuild`, `/apk-add-feature`).
- **End-to-end demo** — generate your own signed sample APK, then exercise the whole pipeline.

---

## Requirements

| Component | Version | Notes |
|---|---|---|
| Windows | 10 or 11 | No Docker, no WSL required |
| Python | 3.10+ | Tested on 3.12 |
| JDK | 17+ | Used by apktool, jadx, keytool, gradle, ghidra |
| Android build-tools | 35.0.0 | `aapt2`, `aapt`, `apksigner`, `zipalign`, `d8`, `dexdump` |
| Android platform-tools | latest | `adb` |
| Android platform | android-35 | `android.jar` for sample builds and Kotlin scaffolds |
| apktool | 2.11.x | Installed under `tools/apktool` |
| jadx | 1.5.x | Installed under `tools/jadx` |

Frida and Ghidra are optional; their tools report a clean "not installed" status when absent.

---

## Quick start

```powershell
# 1. Clone the repository
git clone https://github.com/FMKelana/ReverseAPK.git
cd ReverseAPK

# 2. Install Python 3.12 and JDK 17 (optional, via winget), then apktool and jadx
powershell -ExecutionPolicy Bypass -File scripts/setup-toolchain.ps1 -InstallPrereqs

# Slow GitHub connection? Use a mirror:
powershell -ExecutionPolicy Bypass -File scripts/setup-toolchain.ps1 -MirrorPrefix "https://ghproxy.net/"

# 3. Install Android build-tools, platform-tools, and android-35 without Android Studio
powershell -ExecutionPolicy Bypass -File scripts/setup-android-tools.ps1

# 4. Review or create the machine-specific toolchain config
copy config\toolchain.example.json config\toolchain.json
notepad config\toolchain.json

# 5. Verify every tool
powershell -ExecutionPolicy Bypass -File scripts/verify-toolchain.ps1

# 6. Create the virtual environment and install the server with dev dependencies
python -m venv mcp-server\.venv
mcp-server\.venv\Scripts\python.exe -m pip install -q --upgrade pip
mcp-server\.venv\Scripts\python.exe -m pip install -q -e "mcp-server[dev]"

# 7. Smoke test without an MCP client
mcp-server\.venv\Scripts\python.exe mcp-server\scripts\smoke_server.py

# 8. Run the server over stdio
powershell -ExecutionPolicy Bypass -File scripts/run-mcp.ps1
```

`config/toolchain.json` is machine specific and git-ignored. Empty entries fall back to `PATH`
lookup; `aapt2` additionally enables auto-discovery of the other build-tools in the same folder.

---

## Connect an MCP client

Copy the template, replace `<REPO_ROOT>` with the absolute path to your checkout, and register it
in your MCP client:

```powershell
copy .roo\mcp.json.example .roo\mcp.json
```

```json
{
  "mcpServers": {
    "reverseapk": {
      "command": "<REPO_ROOT>/mcp-server/.venv/Scripts/python.exe",
      "args": ["-m", "reverseapk_mcp"],
      "cwd": "<REPO_ROOT>/mcp-server",
      "env": {
        "REVERSEAPK_HOME": "<REPO_ROOT>",
        "PYTHONPATH": "<REPO_ROOT>/mcp-server/src",
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

Alternative launcher (selects the project venv automatically):

```json
{
  "mcpServers": {
    "reverseapk": {
      "command": "powershell",
      "args": ["-ExecutionPolicy", "Bypass", "-File", "<REPO_ROOT>/scripts/run-mcp.ps1"]
    }
  }
}
```

For Roo Code, the project mode is defined in [`.roomodes`](.roomodes:1), its SOP rules live in
[`.roo/rules-apk-reverse/`](.roo/rules-apk-reverse/01-sop.md:1), and slash commands live in
[`.roo/commands/`](.roo/commands/apk-analyze.md:1).

---

## Configuration

Environment variables (optionally via `mcp-server/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `REVERSEAPK_HOME` | auto-detected repository root | Root that contains `workspaces/`, `samples/`, `tools/`, `config/` |
| `REVERSEAPK_MAX_OUTPUT_BYTES` | `64000` | Output returned to the agent; the remainder is truncated into a log |
| `REVERSEAPK_DEFAULT_TIMEOUT` | `600` | Default per-job timeout in seconds |
| `REVERSEAPK_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |

Toolchain entries in `config/toolchain.json`: `java`, `keytool`, `apktool`, `jadx`, `aapt2`,
`aapt`, `apksigner`, `zipalign`, `dexdump`, `adb`, `gradle`, `frida`, `ghidra_headless`.
Environment variables written as `%REVERSEAPK_HOME%/...` are expanded before use.

---

## Tools

| Group | Tools |
|---|---|
| Environment and sessions | `env_check`, `session_create`, `session_list`, `session_info`, `apk_hash`, `apk_info`, `apk_signature_info` |
| Decoding | `apktool_decode`, `jadx_decompile`, `decode_pipeline`, `manifest_decode`, `smali_list`, `smali_read` |
| Index and search | `index_build`, `code_search`, `code_read`, `callgraph` |
| Build and test | `apktool_build`, `zipalign_apk`, `apksign_apk`, `rebuild_and_sign`, `gradle_build`, `apk_install`, `smoke_test` |
| Advanced analysis | `framework_detect`, `native_lib_list`, `strings_scan`, `dexdump_summary`, `ghidra_headless`, `frida_enumerate`, `frida_run_script` |
| Reconstruction | `jadx_export_gradle`, `kotlin_scaffold`, `fidelity_check`, `reconstruction_plan` |

Every tool returns a uniform JSON envelope:

```json
{
  "status": "ok | partial | error",
  "summary": "short agent-facing summary",
  "artifacts": [{"path": "...", "kind": "apk|json|log|directory", "bytes": 1234}],
  "stats": {},
  "next_steps": ["..."],
  "log_tail": "optional",
  "data": {},
  "error": "optional"
}
```

Full parameter reference: [docs/TOOLS.md](docs/TOOLS.md). Detailed docs are currently written in
Indonesian; translation contributions are welcome.

---

## Recommended workflow

```text
env_check
session_create
apk_info + framework_detect + apk_signature_info
decode_pipeline
manifest_decode + index_build
code_search + callgraph
  ├─ Path A: patch smali → apktool_build → zipalign_apk → apksign_apk
  └─ Path B: jadx_export_gradle / kotlin_scaffold → gradle_build
smoke_test + fidelity_check
reconstruction_plan
```

See [docs/WORKFLOW.md](docs/WORKFLOW.md) for the full phase-by-phase guide.

---

## Demo

The repository ships a generator for its own signed sample APK, so the pipeline can be tested
without third-party applications. The generated files stay out of Git.

```powershell
# Build a signed sample APK at samples\demo.apk
powershell -ExecutionPolicy Bypass -File scripts/build-sample-apk.ps1

# Run the whole MCP pipeline against it
mcp-server\.venv\Scripts\python.exe mcp-server\scripts\e2e_demo.py samples\demo.apk
```

Expected result: a new session under `workspaces/` containing a decoded APK, a searchable index,
a rebuilt and signed APK, and a fidelity report.

---

## Project structure

```text
ReverseAPK/
├─ .roomodes                  # Roo Code custom mode: apk-reverse
├─ .roo/                      # MCP config template, SOP rules, slash commands
├─ config/                    # toolchain.json (local) and toolchain.example.json
├─ docs/                      # tool reference, workflow, troubleshooting
├─ mcp-server/
│  ├─ scripts/                # smoke test and end-to-end demo
│  ├─ src/reverseapk_mcp/     # server, adapters, tools, indexer
│  └─ tests/                  # unit and integration tests
├─ samples/                   # locally generated test APKs (git-ignored)
├─ scripts/                   # toolchain setup, verification, sample APK builder
├─ tools/                     # downloaded binaries (git-ignored)
└─ workspaces/                # per-session artifacts (git-ignored)
```

---

## Running the tests

```powershell
mcp-server\.venv\Scripts\python.exe -m pytest mcp-server\tests -q
```

The suite is self-contained (23 tests) and does not require an Android device or a network
connection. It creates temporary APK fixtures and a temporary workspace.

---

## Contributing

Contributions are welcome — new adapters, new MCP tools, documentation, and translations.
Start with [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, coding conventions,
and pull request checklist.

Ideas that are especially useful:

- Linux and macOS support for the path and process layers.
- Additional adapters (for example `apkid`, `baksmali`, `objection`).
- English translations of `docs/`.
- CI coverage for the test suite.

---

## Security

Reverse engineering involves untrusted input. Please read [SECURITY.md](SECURITY.md) before
processing APKs you did not build yourself. Never commit keystores, `.env` files, or
`config/toolchain.json`; all three are git-ignored.

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

---

## License

Released under the [MIT License](LICENSE). Third-party binaries downloaded by the setup scripts
remain under their own licenses (Apache 2.0 for apktool and Android SDK tools, Apache 2.0 for jadx).
