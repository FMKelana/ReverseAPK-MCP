"""Smoke test untuk komponen inti ReverseAPK MCP."""

from __future__ import annotations

import asyncio
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from reverseapk_mcp.adapters.aapt2 import parse_badging
from reverseapk_mcp.config import (
    PathNotAllowedError,
    ensure_within,
    load_settings,
    reset_settings_cache,
)
from reverseapk_mcp.jobs import CommandRejectedError, run_command
from reverseapk_mcp.schemas import failure, success
from reverseapk_mcp.tools import inventory, session

BADGING_OUTPUT = """package: name='com.example.demo' versionCode='42' versionName='1.4.2'
sdkVersion:'24'
targetSdkVersion:'34'
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.CAMERA'
uses-feature: name='android.hardware.camera'
uses-feature-not-required: name='android.hardware.nfc'
application-label:'Demo App'
application-debuggable
launchable-activity: name='com.example.demo.MainActivity'  label='' icon=''
native-code: 'arm64-v8a' 'armeabi-v7a'
densities: '160' '240'
"""


class FakeMCP:
    """Menangkap fungsi yang didaftarkan oleh modul tool."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}
        self.resources: dict[str, Any] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator

    def resource(self, uri: str, mime_type: str | None = None):
        def decorator(func):
            self.resources[uri] = func
            return func

        return decorator


def _build_home(tmp_path: Path) -> Path:
    home = tmp_path / "repo"
    (home / "config").mkdir(parents=True)
    (home / "samples").mkdir(parents=True)
    (home / "workspaces").mkdir(parents=True)
    (home / "config" / "toolchain.json").write_text(
        json.dumps({"aapt2": "", "jadx": ""}), encoding="utf-8"
    )
    return home


def _build_apk(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"\x03\x00\x08\x00binary")
        archive.writestr("classes.dex", b"dex\n035\x00")
        archive.writestr("classes2.dex", b"dex\n035\x00")
        archive.writestr("lib/arm64-v8a/libfoo.so", b"\x7fELF")
        archive.writestr("assets/flutter_assets/AssetManifest.json", b"{}")
    return path


def test_parse_badging_extracts_metadata() -> None:
    parsed = parse_badging(BADGING_OUTPUT)

    assert parsed["package"] == "com.example.demo"
    assert parsed["version_code"] == 42
    assert parsed["version_name"] == "1.4.2"
    assert parsed["min_sdk"] == 24
    assert parsed["target_sdk"] == 34
    assert parsed["label"] == "Demo App"
    assert parsed["debuggable"] is True
    assert parsed["launchable_activity"] == "com.example.demo.MainActivity"
    assert parsed["permissions"] == [
        "android.permission.INTERNET",
        "android.permission.CAMERA",
    ]
    assert parsed["native_code"] == ["arm64-v8a", "armeabi-v7a"]
    assert {"name": "android.hardware.camera", "required": True} in parsed["features"]


def test_ensure_within_blocks_traversal(tmp_path: Path) -> None:
    root = tmp_path / "workspaces"
    root.mkdir()

    allowed = ensure_within(root / "session" / "manifest.json", [root])
    assert allowed.is_relative_to(root.resolve())

    with pytest.raises(PathNotAllowedError):
        ensure_within(tmp_path / "outside.json", [root])


def test_load_settings_reads_toolchain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _build_home(tmp_path)
    monkeypatch.setenv("REVERSEAPK_HOME", str(home))
    monkeypatch.setenv("REVERSEAPK_MAX_OUTPUT_BYTES", "4096")
    reset_settings_cache()

    settings = load_settings()

    assert settings.home == home.resolve()
    assert settings.config_path == home.resolve() / "config" / "toolchain.json"
    assert settings.toolchain.entries["jadx"] == ""
    assert settings.max_output_bytes == 4096
    reset_settings_cache()


def test_tool_result_serialization() -> None:
    ok_payload = json.loads(success("selesai", stats={"files": 2}).to_json())
    assert ok_payload["status"] == "ok"
    assert ok_payload["stats"] == {"files": 2}
    assert "error" not in ok_payload

    error_payload = json.loads(failure("gagal", "penyebab").to_json())
    assert error_payload["status"] == "error"
    assert error_payload["error"] == "penyebab"


def test_detect_framework() -> None:
    assert inventory.detect_framework(["assets/flutter_assets/a.json", "classes.dex"]) == "flutter"
    assert inventory.detect_framework(["assets/index.android.bundle"]) == "react-native"
    assert inventory.detect_framework(["lib/arm64-v8a/libfoo.so"]) == "native"
    assert inventory.detect_framework(["classes.dex"]) == "unknown"


def test_scan_archive_counts(tmp_path: Path) -> None:
    apk = _build_apk(tmp_path / "demo.apk")
    result = inventory.scan_archive(apk)

    assert result["dex_files"] == ["classes.dex", "classes2.dex"]
    assert result["abis"] == ["arm64-v8a"]
    assert result["native_lib_count"] == 1
    assert result["framework"] == "flutter"


def test_session_and_inventory_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _build_home(tmp_path)
    apk = _build_apk(home / "samples" / "demo.apk")
    monkeypatch.setenv("REVERSEAPK_HOME", str(home))
    reset_settings_cache()

    fake = FakeMCP()
    session.register(fake)
    inventory.register(fake)

    created = json.loads(
        asyncio.run(fake.tools["session_create"](apk_path="samples/demo.apk", copy_apk=True))
    )
    assert created["status"] == "ok"
    session_id = created["data"]["session_id"]
    manifest_file = Path(created["data"]["manifest"])
    assert manifest_file.is_file()
    assert created["data"]["apk"]["workspace_path"] == "input/demo.apk"

    info = json.loads(asyncio.run(fake.tools["apk_info"](session_id=session_id)))
    assert info["status"] in {"ok", "partial"}
    assert info["data"]["archive"]["framework"] == "flutter"
    assert info["stats"]["dex_files"] == 2

    listed = json.loads(asyncio.run(fake.tools["session_list"]()))
    assert listed["stats"]["count"] == 1

    hashed = json.loads(asyncio.run(fake.tools["apk_hash"](session_id=session_id)))
    assert hashed["status"] == "ok"
    assert hashed["data"]["changed"] is False

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["session_id"] == session_id
    assert any(step["name"] == "apk_info" for step in manifest["steps"])


def test_session_create_rejects_non_apk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _build_home(tmp_path)
    (home / "samples" / "notes.txt").write_text("bukan apk", encoding="utf-8")
    monkeypatch.setenv("REVERSEAPK_HOME", str(home))
    reset_settings_cache()

    fake = FakeMCP()
    session.register(fake)

    result = json.loads(asyncio.run(fake.tools["session_create"](apk_path="samples/notes.txt")))
    assert result["status"] == "error"


def test_run_command_rejects_control_characters() -> None:
    with pytest.raises(CommandRejectedError):
        asyncio.run(run_command(["cmd", "argumen\nberbahaya"]))


def test_run_command_captures_output() -> None:
    result = asyncio.run(run_command(["python", "-c", "print('halo')"], timeout=30))
    assert result.ok is True
    assert "halo" in result.stdout
