"""Entry point MCP server ReverseAPK.

Server berjalan di atas transport stdio sehingga bisa didaftarkan langsung
sebagai MCP server pada Roo Code atau MCP client lain.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

try:  # SDK MCP v2
    from mcp.server import MCPServer as _MCPServer
except ImportError:  # SDK MCP v1
    from mcp.server.fastmcp import FastMCP as _MCPServer  # type: ignore[assignment]

from . import resources
from .config import get_settings
from .tools import register_all

LOGGER = logging.getLogger("reverseapk")
SERVER_NAME = "reverseapk"

SERVER_INSTRUCTIONS = """\
Server ini menyediakan tooling reverse engineering APK Android di Windows:
inventaris APK, dekode apktool dan jadx, indeks pencarian kode, build dan signing,
serta analisis dinamis opsional.

Alur kerja yang disarankan:
1. Panggil env_check untuk memastikan toolchain siap.
2. Buat sesi dengan session_create, lalu baca metadata dengan apk_info.
3. Lanjutkan decode statis dan index sebelum membaca kode secara detail.
4. Selalu bekerja di dalam workspace sesi dan catat langkah penting ke manifest.

Batasan: hanya APK milik sendiri atau yang Anda punya izin untuk dianalisis.
"""


def build_server() -> Any:
    settings = get_settings()

    try:
        server = _MCPServer(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    except TypeError:  # versi SDK tanpa parameter instructions
        server = _MCPServer(SERVER_NAME)

    register_all(server)
    resources.register(server)

    LOGGER.debug("Server %s siap dengan home=%s", SERVER_NAME, settings.home)
    return server


def main() -> None:
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    LOGGER.info("ReverseAPK MCP server start. home=%s config=%s", settings.home, settings.config_path)
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
