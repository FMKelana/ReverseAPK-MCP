"""Smoke test MCP server tanpa client eksternal.

Membangun server, menampilkan tool dan resource yang terdaftar, lalu memanggil
``env_check`` untuk memastikan pipeline eksekusi bekerja.

Jalankan dari root repository:

    mcp-server\\.venv\\Scripts\\python.exe mcp-server\\scripts\\smoke_server.py

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

from reverseapk_mcp.server import build_server  # noqa: E402


def _first_text(result: Any) -> str:
    if isinstance(result, tuple):
        result = result[0]
    if hasattr(result, "content"):
        result = result.content
    if isinstance(result, str):
        return result
    for item in result or []:
        text = getattr(item, "text", None)
        if text:
            return str(text)
    return ""


async def main() -> int:
    server = build_server()

    tools = await server.list_tools()
    print("TOOLS  :", ", ".join(sorted(getattr(tool, "name", "?") for tool in tools)))

    try:
        templates = await server.list_resource_templates()
        uris = sorted(
            str(getattr(item, "uriTemplate", None) or getattr(item, "uri_template", "?"))
            for item in templates
        )
        print("RESOURCE:", ", ".join(uris))
    except Exception as exc:  # pragma: no cover - hanya diagnostik
        print("RESOURCE: gagal dibaca:", exc)

    raw = _first_text(await server.call_tool("env_check", {"include_versions": False}))
    payload = json.loads(raw) if raw else {}
    print("ENV_CHECK:", payload.get("status"), "-", payload.get("summary"))

    missing = [
        row["tool"]
        for row in payload.get("data", {}).get("tools", [])
        if row.get("required") and not row.get("available")
    ]
    if missing:
        print("MISSING :", ", ".join(missing))

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
