"""Adapter keytool untuk membuat keystore debug lokal."""

from __future__ import annotations

import os
from pathlib import Path

from ..jobs import CommandResult
from .base import AdapterError, BaseAdapter


class KeytoolAdapter(BaseAdapter):
    name = "keytool"
    aliases = ("keytool",)
    version_args = ("-help",)

    @property
    def executable(self) -> str | None:
        resolved = super().executable
        if resolved:
            return resolved

        suffix = ".exe" if os.name == "nt" else ""
        candidates: list[Path] = []

        java = self.settings.toolchain.resolve("java", ("java",))
        if java:
            candidates.append(Path(java).parent / f"keytool{suffix}")

        java_home = os.environ.get("JAVA_HOME", "").strip()
        if java_home:
            candidates.append(Path(java_home) / "bin" / f"keytool{suffix}")

        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return None

    async def create_debug_keystore(
        self,
        keystore_path: Path,
        *,
        alias: str = "androiddebugkey",
        storepass: str = "android",
        keypass: str = "android",
        dname: str = "CN=Android Debug,O=Android,C=US",
        validity_days: int = 10000,
        timeout: float | None = None,
    ) -> CommandResult:
        if keystore_path.is_file():
            return CommandResult(
                command=["keytool", "reuse"],
                exit_code=0,
                stdout="keystore sudah ada",
                stderr="",
                duration=0.0,
            )

        keystore_path.parent.mkdir(parents=True, exist_ok=True)
        arguments = [
            "-genkeypair",
            "-v",
            "-keystore",
            str(keystore_path),
            "-storepass",
            storepass,
            "-keypass",
            keypass,
            "-alias",
            alias,
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            str(validity_days),
            "-dname",
            dname,
        ]

        result = await self.run(arguments, timeout=timeout)
        if not result.ok or not keystore_path.is_file():
            raise AdapterError(
                f"keytool gagal membuat keystore dengan kode {result.exit_code}: {result.tail(1500)}"
            )
        return result
