"""Adapter adb untuk instalasi dan pengujian di emulator atau device."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..jobs import CommandResult
from .base import AdapterError, BaseAdapter


class AdbAdapter(BaseAdapter):
    name = "adb"
    aliases = ("adb",)
    version_args = ("version",)

    def _args(self, arguments: list[str], device: str | None) -> list[str]:
        if device:
            return ["-s", device, *arguments]
        return arguments

    async def devices(self, *, timeout: float | None = 30) -> list[dict[str, Any]]:
        result = await self.run(["devices", "-l"], timeout=timeout)
        if not result.ok:
            raise AdapterError(f"adb devices gagal: {result.tail(1000)}")

        devices: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices") or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            entry: dict[str, Any] = {"serial": parts[0], "state": parts[1]}
            for token in parts[2:]:
                if ":" in token:
                    key, value = token.split(":", 1)
                    entry[key] = value
            devices.append(entry)
        return devices

    async def install(
        self,
        apk_path: Path,
        *,
        device: str | None = None,
        reinstall: bool = True,
        timeout: float | None = 180,
    ) -> CommandResult:
        if not apk_path.is_file():
            raise AdapterError(f"APK tidak ditemukan: {apk_path}")
        arguments = ["install", "-t"]
        if reinstall:
            arguments.append("-r")
        arguments.append(str(apk_path))

        result = await self.run(self._args(arguments, device), timeout=timeout)
        if not result.ok or "Success" not in result.combined():
            raise AdapterError(f"adb install gagal: {result.tail(1500)}")
        return result

    async def uninstall(
        self,
        package: str,
        *,
        device: str | None = None,
        timeout: float | None = 60,
    ) -> CommandResult:
        return await self.run(self._args(["uninstall", package], device), timeout=timeout)

    async def start_activity(
        self,
        component: str,
        *,
        device: str | None = None,
        timeout: float | None = 45,
    ) -> CommandResult:
        return await self.run(
            self._args(["shell", "am", "start", "-W", "-n", component], device),
            timeout=timeout,
        )

    async def logcat_dump(
        self,
        *,
        lines: int = 200,
        device: str | None = None,
        timeout: float | None = 45,
    ) -> CommandResult:
        return await self.run(
            self._args(["logcat", "-d", "-t", str(max(1, lines))], device), timeout=timeout
        )

    async def is_installed(
        self,
        package: str,
        *,
        device: str | None = None,
        timeout: float | None = 30,
    ) -> bool:
        result = await self.run(
            self._args(["shell", "pm", "list", "packages", package], device), timeout=timeout
        )
        return f"package:{package}" in result.combined()
