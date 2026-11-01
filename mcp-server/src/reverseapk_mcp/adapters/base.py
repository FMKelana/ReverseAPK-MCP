"""Basis adapter untuk membungkus CLI toolchain."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ..config import Settings, ensure_within
from ..jobs import CommandResult, run_command


class ToolNotFoundError(RuntimeError):
    """Executable tool tidak ditemukan pada konfigurasi maupun PATH."""


class AdapterError(RuntimeError):
    """Tool ditemukan tetapi gagal dieksekusi atau mengembalikan error."""


class BaseAdapter:
    """Membungkus satu executable agar aman dipanggil dari tool MCP."""

    name: str = "tool"
    aliases: tuple[str, ...] = ()
    version_args: tuple[str, ...] = ("--version",)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def executable(self) -> str | None:
        return self.settings.toolchain.resolve(self.name, self.aliases)

    @property
    def available(self) -> bool:
        return self.executable is not None

    def require_executable(self) -> str:
        executable = self.executable
        if not executable:
            raise ToolNotFoundError(
                f"Tool '{self.name}' tidak ditemukan. Isi path pada config/toolchain.json "
                f"atau pastikan tool ada di PATH."
            )
        return executable

    async def run(
        self,
        arguments: Sequence[str],
        *,
        cwd: str | Path | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        executable = self.require_executable()

        workdir: Path | None = None
        if cwd is not None:
            workdir = ensure_within(cwd, [self.settings.workspace_root], "cwd")
            workdir.mkdir(parents=True, exist_ok=True)

        return await run_command(
            [executable, *arguments],
            cwd=workdir,
            timeout=timeout if timeout is not None else self.settings.default_timeout,
            max_output_bytes=self.settings.max_output_bytes,
        )

    async def version(self, timeout: float = 20.0) -> str | None:
        if not self.available:
            return None
        try:
            result = await self.run(list(self.version_args), timeout=timeout)
        except ToolNotFoundError:
            return None

        for line in result.combined().splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
        return None
