"""Job runner async untuk eksekusi CLI toolchain.

Aturan penting:

* Tidak pernah memakai ``shell=True``.
* Argumen selalu berupa list sehingga tidak bisa disisipi perintah tambahan.
* Proses yang melewati timeout dihentikan beserta child process.
* Output dipotong agar tidak membanjiri context agent.
"""

from __future__ import annotations

import asyncio
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

IS_WINDOWS = os.name == "nt"
# Karakter yang berbahaya jika argumen dieksekusi melalui cmd.exe pada wrapper .bat.
_CMD_UNSAFE_CHARS = set('&|<>^%"')


class CommandRejectedError(RuntimeError):
    """Argumen perintah ditolak karena berpotensi tidak aman."""


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.exit_code == 0

    def combined(self) -> str:
        parts = [part.strip() for part in (self.stdout, self.stderr) if part and part.strip()]
        return "\n".join(parts)

    def tail(self, max_chars: int = 4_000) -> str:
        text = self.combined()
        if len(text) <= max_chars:
            return text
        return "...[dipotong]...\n" + text[-max_chars:]

    def describe(self) -> str:
        return subprocess_list2cmdline(self.command)


def subprocess_list2cmdline(command: Sequence[str]) -> str:
    import subprocess

    return subprocess.list2cmdline(list(command))


def _truncate(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    head_budget = max_bytes // 4
    tail_budget = max_bytes - head_budget
    head = encoded[:head_budget].decode("utf-8", errors="ignore")
    tail = encoded[-tail_budget:].decode("utf-8", errors="ignore")
    omitted = len(encoded) - head_budget - tail_budget
    return f"{head}\n...[output dipotong {omitted} byte]...\n{tail}"


def _validate_arguments(command: Sequence[str]) -> None:
    for item in command:
        if not isinstance(item, str):
            raise CommandRejectedError("Semua argumen perintah harus berupa string.")
        if not item:
            raise CommandRejectedError("Argumen perintah tidak boleh kosong.")
        if any(char in item for char in ("\x00", "\r", "\n")):
            raise CommandRejectedError(f"Argumen mengandung karakter kontrol: {item!r}")


def _normalize_command(command: Sequence[str]) -> list[str]:
    """Bungkus file .bat/.cmd dengan cmd.exe agar bisa dieksekusi di Windows."""

    normalized = list(command)
    executable = Path(normalized[0])
    suffix = executable.suffix.lower()

    if IS_WINDOWS and suffix in {".bat", ".cmd"}:
        for argument in normalized[1:]:
            if any(char in argument for char in _CMD_UNSAFE_CHARS):
                raise CommandRejectedError(
                    f"Argumen {argument!r} mengandung karakter yang tidak aman untuk wrapper batch."
                )
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        return [comspec, "/d", "/s", "/c", *normalized]

    return normalized


async def _terminate_process_tree(pid: int) -> None:
    if IS_WINDOWS:
        try:
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/F",
                "/T",
                "/PID",
                str(pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
            return
        except (OSError, FileNotFoundError):
            pass

    try:
        os.kill(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


async def run_command(
    command: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout: float = 600.0,
    env: dict[str, str] | None = None,
    max_output_bytes: int = 64_000,
) -> CommandResult:
    """Jalankan perintah CLI dan kembalikan hasilnya.

    Args:
        command: daftar argumen, elemen pertama adalah executable.
        cwd: direktori kerja, harus sudah divalidasi pemanggil.
        timeout: batas waktu detik.
        env: variabel environment tambahan.
        max_output_bytes: batas ukuran stdout dan stderr yang dipertahankan.
    """

    if not command:
        raise CommandRejectedError("Perintah kosong tidak diizinkan.")

    _validate_arguments(command)
    normalized = _normalize_command(command)

    process_env = os.environ.copy()
    process_env.setdefault("PYTHONUTF8", "1")
    process_env.setdefault("PYTHONIOENCODING", "utf-8")
    if env:
        process_env.update(env)

    creationflags = 0
    if IS_WINDOWS:
        creationflags = getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)

    started = time.monotonic()
    process = await asyncio.create_subprocess_exec(
        *normalized,
        cwd=str(cwd) if cwd is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=process_env,
        creationflags=creationflags,
    )

    timed_out = False
    stdout_bytes = b""
    stderr_bytes = b""

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        timed_out = True
        await _terminate_process_tree(process.pid)
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=10)
        except (asyncio.TimeoutError, ValueError):
            stdout_bytes, stderr_bytes = b"", b""

    duration = time.monotonic() - started

    stdout_text = _truncate(stdout_bytes.decode("utf-8", errors="replace"), max_output_bytes)
    stderr_text = _truncate(stderr_bytes.decode("utf-8", errors="replace"), max_output_bytes)

    return CommandResult(
        command=normalized,
        exit_code=process.returncode,
        stdout=stdout_text,
        stderr=stderr_text,
        duration=duration,
        timed_out=timed_out,
    )
