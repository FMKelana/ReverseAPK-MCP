"""Demo end-to-end pipeline ReverseAPK memakai APK sampel.

Prasyarat: APK hasil ``scripts/build-sample-apk.ps1`` tersedia di samples/.

Jalankan dari root repository:

    mcp-server\\.venv\\Scripts\\python.exe mcp-server\\scripts\\e2e_demo.py samples/demo.apk

`REVERSEAPK_HOME` opsional; bila kosong, root repository dideteksi otomatis.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from reverseapk_mcp.tools import (  # noqa: E402
    analysis,
    build,
    decode,
    environment,
    inventory,
    reconstruct,
    search,
    session,
)


class Registry:
    """Registry minimal untuk menangkap tool tanpa MCP client."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


async def call(registry: Registry, name: str, **kwargs: Any) -> dict[str, Any]:
    raw = await registry.tools[name](**kwargs)
    payload = json.loads(raw)
    status = payload.get("status")
    print(f"[{name}] {status}: {payload.get('summary')}")
    if payload.get("error"):
        print(f"    error: {payload['error']}")
    if payload.get("next_steps"):
        for step in payload["next_steps"][:3]:
            print(f"    next: {step}")
    return payload


async def main() -> int:
    registry = Registry()
    for module in (environment, session, inventory, decode, search, build, analysis, reconstruct):
        module.register(registry)

    apk = sys.argv[1] if len(sys.argv) > 1 else "samples/demo.apk"

    env = await call(registry, "env_check", include_versions=False)
    if env.get("status") != "ok":
        print("Toolchain belum lengkap, hentikan demo.")
        return 1

    created = await call(registry, "session_create", apk_path=apk, copy_apk=True)
    if created.get("status") != "ok":
        return 1

    session_id = created["data"]["session_id"]
    print(f"    session_id: {session_id}")

    await call(registry, "apk_info", session_id=session_id)
    await call(registry, "framework_detect", session_id=session_id)
    await call(registry, "decode_pipeline", session_id=session_id)
    await call(registry, "manifest_decode", session_id=session_id)
    await call(registry, "index_build", session_id=session_id)
    await call(registry, "code_search", session_id=session_id, query="ENDPOINT")
    await call(registry, "smali_list", session_id=session_id, query="MainActivity")
    await call(registry, "apktool_build", session_id=session_id)
    await call(registry, "rebuild_and_sign", session_id=session_id)
    await call(registry, "fidelity_check", session_id=session_id)
    await call(registry, "reconstruction_plan", session_id=session_id)

    print()
    print(f"Selesai. Periksa workspace: workspaces/{session_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
