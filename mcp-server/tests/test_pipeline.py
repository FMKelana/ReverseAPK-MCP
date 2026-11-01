"""Test integrasi pipeline M3 sampai M7 tanpa membutuhkan APK nyata."""

from __future__ import annotations

import asyncio
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from reverseapk_mcp.config import reset_settings_cache
from reverseapk_mcp.indexer.db import build_index, index_stats, references, search
from reverseapk_mcp.tools import analysis, decode, reconstruct, session
from reverseapk_mcp.tools import search as search_tools

MANIFEST_XML = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.demo"
    android:versionCode="42"
    android:versionName="1.4.2">
    <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.CAMERA" />
    <application android:label="Demo" android:debuggable="true">
        <activity android:name="com.example.demo.MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        <service android:name=".SyncService" android:exported="false" />
        <receiver android:name=".BootReceiver" android:exported="true" />
        <provider android:name=".DataProvider" android:authorities="com.example.demo.provider" />
    </application>
</manifest>
"""

JAVA_SOURCE = """package com.example.demo;

public class MainActivity extends Activity {
    private String token = "secret-token-value";

    public void onCreate(Bundle savedInstanceState) {
        String url = "https://api.example.com/v1/login";
        helper.compute(42);
    }
}
"""

SMALI_SOURCE = """.class public Lcom/example/demo/Helper;
.super Ljava/lang/Object;

.method public static compute(I)I
    .locals 1
    const-string v0, "smali-secret"
    return v0
.end method
"""

STRINGS_XML = """<resources>
    <string name="app_name">Demo App</string>
    <string name="login_title">Masuk</string>
</resources>
"""


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def _call(fake: FakeMCP, name: str, **kwargs: Any) -> dict[str, Any]:
    return json.loads(asyncio.run(fake.tools[name](**kwargs)))


def _make_apk(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"\x03\x00\x08\x00binary")
        archive.writestr("classes.dex", b"dex\n035\x00")
        archive.writestr("lib/arm64-v8a/libfoo.so", b"\x7fELF" + b"api.example.com\x00" * 3)
        archive.writestr("assets/flutter_assets/AssetManifest.json", b"{}")
        archive.writestr(
            "assets/config.txt",
            b"endpoint=https://api.example.com/v1/login\nsecret=super-secret-key\n",
        )
    return path


def _write_session_tree(session_root: Path) -> None:
    (session_root / "apktool").mkdir(parents=True, exist_ok=True)
    (session_root / "apktool/AndroidManifest.xml").write_text(MANIFEST_XML, encoding="utf-8")

    smali_dir = session_root / "apktool/smali/com/example/demo"
    smali_dir.mkdir(parents=True, exist_ok=True)
    (smali_dir / "Helper.smali").write_text(SMALI_SOURCE, encoding="utf-8")

    values_dir = session_root / "apktool/res/values"
    values_dir.mkdir(parents=True, exist_ok=True)
    (values_dir / "strings.xml").write_text(STRINGS_XML, encoding="utf-8")

    java_dir = session_root / "jadx/sources/com/example/demo"
    java_dir.mkdir(parents=True, exist_ok=True)
    (java_dir / "MainActivity.java").write_text(JAVA_SOURCE, encoding="utf-8")


@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "repo"
    (home / "config").mkdir(parents=True)
    (home / "samples").mkdir()
    (home / "workspaces").mkdir()
    (home / "config/toolchain.json").write_text("{}", encoding="utf-8")
    _make_apk(home / "samples/demo.apk")

    monkeypatch.setenv("REVERSEAPK_HOME", str(home))
    reset_settings_cache()

    fake = FakeMCP()
    session.register(fake)
    decode.register(fake)
    search_tools.register(fake)
    analysis.register(fake)
    reconstruct.register(fake)

    created = _call(fake, "session_create", apk_path="samples/demo.apk", copy_apk=True)
    assert created["status"] == "ok"
    session_id = created["data"]["session_id"]
    _write_session_tree(home / "workspaces" / session_id)

    yield home, session_id, fake
    reset_settings_cache()


def test_manifest_decode_parses_components(workspace) -> None:
    _, session_id, fake = workspace
    result = _call(fake, "manifest_decode", session_id=session_id)

    assert result["status"] == "ok"
    manifest = result["data"]["manifest"]
    assert manifest["package"] == "com.example.demo"
    assert manifest["version_code"] == 42
    assert manifest["min_sdk"] == 24
    assert set(manifest["permissions"]) == {
        "android.permission.INTERNET",
        "android.permission.CAMERA",
    }
    assert manifest["activities"][0]["name"] == "com.example.demo.MainActivity"
    assert manifest["services"][0]["name"] == ".SyncService"
    assert manifest["providers"][0]["authorities"] == "com.example.demo.provider"


def test_index_build_and_search(workspace) -> None:
    home, session_id, fake = workspace
    built = _call(fake, "index_build", session_id=session_id)

    assert built["status"] == "ok"
    assert built["stats"]["files"] >= 3

    classes = _call(fake, "code_search", session_id=session_id, query="MainActivity", kind="class")
    assert classes["status"] == "ok"
    assert any(item["name"] == "MainActivity" for item in classes["data"]["results"])

    methods = _call(fake, "code_search", session_id=session_id, query="compute", kind="method")
    assert any(item["parent"] == "com.example.demo.Helper" for item in methods["data"]["results"])

    strings = _call(fake, "code_search", session_id=session_id, query="api.example.com")
    assert strings["status"] == "ok"
    assert any("api.example.com" in item["name"] for item in strings["data"]["results"])

    resources = _call(fake, "code_search", session_id=session_id, query="app_name", kind="resource")
    assert any(item["name"] == "app_name" for item in resources["data"]["results"])

    references_result = _call(fake, "callgraph", session_id=session_id, symbol="onCreate")
    assert references_result["status"] == "ok"
    assert references_result["stats"]["references"] >= 1

    db_path = home / "workspaces" / session_id / "index.db"
    assert db_path.is_file()
    assert index_stats(db_path)["symbols"] > 0


def test_code_read_blocks_traversal(workspace) -> None:
    _, session_id, fake = workspace

    blocked = _call(fake, "code_read", session_id=session_id, path="../manifest.json")
    assert blocked["status"] == "error"

    allowed = _call(
        fake,
        "code_read",
        session_id=session_id,
        path="jadx/sources/com/example/demo/MainActivity.java",
        start_line=1,
        end_line=20,
    )
    assert allowed["status"] == "ok"
    assert "secret-token-value" in allowed["data"]["content"]


def test_smali_list_and_read(workspace) -> None:
    _, session_id, fake = workspace

    listed = _call(fake, "smali_list", session_id=session_id, query="helper")
    assert listed["stats"]["total"] == 1
    path = listed["data"]["files"][0]["path"]
    assert path.endswith("Helper.smali")

    read = _call(fake, "smali_read", session_id=session_id, path=path, start_line=1, end_line=50)
    assert read["status"] == "ok"
    assert ".method public static compute" in read["data"]["content"]

    traversal = _call(fake, "smali_read", session_id=session_id, path="../../config/toolchain.json")
    assert traversal["status"] == "error"


def test_strings_scan_and_framework(workspace) -> None:
    _, session_id, fake = workspace

    framework = _call(fake, "framework_detect", session_id=session_id)
    assert framework["data"]["framework"] == "flutter"

    scan = _call(fake, "strings_scan", session_id=session_id, query="api.example.com", limit=20)
    assert scan["status"] == "ok"
    assert any("api.example.com" in item["value"] for item in scan["data"]["matches"])

    native = _call(fake, "native_lib_list", session_id=session_id, extract=True)
    assert native["stats"]["libraries"] == 1
    assert native["data"]["extracted"]


def test_kotlin_scaffold_and_plan(workspace) -> None:
    home, session_id, fake = workspace

    _call(fake, "manifest_decode", session_id=session_id)
    _call(fake, "index_build", session_id=session_id)

    scaffold = _call(
        fake,
        "kotlin_scaffold",
        session_id=session_id,
        package_name="com.example.reimpl",
        app_name="Demo Reimpl",
    )
    assert scaffold["status"] == "ok"

    project_root = home / "workspaces" / session_id / "build/reimplement"
    assert (project_root / "settings.gradle.kts").is_file()
    assert (project_root / "app/build.gradle.kts").is_file()
    assert (project_root / "app/src/main/AndroidManifest.xml").is_file()
    assert (project_root / "app/src/main/java/com/example/reimpl/MainActivity.kt").is_file()

    app_gradle = (project_root / "app/build.gradle.kts").read_text(encoding="utf-8")
    assert 'namespace = "com.example.reimpl"' in app_gradle

    manifest_xml = (project_root / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert "android.permission.CAMERA" in manifest_xml

    plan = _call(fake, "reconstruction_plan", session_id=session_id)
    assert plan["status"] == "ok"
    plan_path = home / "workspaces" / session_id / plan["data"]["plan"]
    assert plan_path.is_file()
    assert "com.example.demo" in plan_path.read_text(encoding="utf-8")


def test_fidelity_check_without_rebuild(workspace) -> None:
    _, session_id, fake = workspace
    result = _call(fake, "fidelity_check", session_id=session_id)
    assert result["status"] == "partial"
    assert "rebuild" in result["summary"].lower()


def test_compare_fidelity_scores() -> None:
    original = {
        "package": "com.example.demo",
        "version_name": "1.4.2",
        "min_sdk": 24,
        "target_sdk": 34,
        "permissions": ["android.permission.INTERNET"],
        "launchable_activity": "com.example.demo.MainActivity",
        "activities": [{"name": "com.example.demo.MainActivity"}],
        "services": [],
        "receivers": [],
        "providers": [],
    }
    rebuilt = {
        "package": "com.example.demo",
        "version_name": "1.4.2",
        "min_sdk": 24,
        "target_sdk": 34,
        "permissions": ["android.permission.INTERNET", "android.permission.CAMERA"],
        "launchable_activity": "com.example.demo.MainActivity",
        "activities": [{"name": "com.example.demo.MainActivity"}],
        "services": [],
        "receivers": [],
        "providers": [],
    }

    report = reconstruct.compare_fidelity(original, rebuilt)
    assert report["total"] >= 6
    assert 0.0 < report["score"] < 1.0
    permission_check = next(item for item in report["checks"] if item["check"] == "permissions")
    assert permission_check["ok"] is False
    assert "android.permission.CAMERA" in permission_check["detail"]["extra"]


def test_indexer_search_direct(tmp_path: Path) -> None:
    java_dir = tmp_path / "jadx"
    java_dir.mkdir()
    (java_dir / "TokenStore.java").write_text(JAVA_SOURCE, encoding="utf-8")

    db_path = tmp_path / "index.db"
    stats = build_index(db_path, [(java_dir, "java", "java")], base_dir=tmp_path)

    assert stats.files == 1
    assert stats.symbols >= 3

    results = search(db_path, "MainActivity", kind="class")
    assert results
    assert results[0]["name"] == "MainActivity"

    refs = references(db_path, "token", limit=5)
    assert isinstance(refs, list)
    assert refs


def test_find_launch_component(tmp_path: Path) -> None:
    from reverseapk_mcp.tools.build import _launch_component

    session_root = tmp_path / "session"
    session_root.mkdir()
    decoded = {
        "package": "com.example.demo",
        "activities": [
            {
                "name": ".SplashActivity",
                "intent_filters": [
                    {
                        "actions": ["android.intent.action.MAIN"],
                        "categories": ["android.intent.category.LAUNCHER"],
                    }
                ],
            }
        ],
    }
    (session_root / "manifest-decoded.json").write_text(json.dumps(decoded), encoding="utf-8")

    assert _launch_component(session_root, "com.example.demo") == "com.example.demo/com.example.demo.SplashActivity"
    assert (
        _launch_component(session_root, "com.example.demo", ".Other")
        == "com.example.demo/com.example.demo.Other"
    )


APKTOOL_YML = """version: 2.11.1
apkFileName: demo.apk
isFrameworkApk: false
sdkInfo:
  minSdkVersion: 24
  targetSdkVersion: 35
packageInfo:
  forcedPackageId: 127
versionInfo:
  versionCode: 7
  versionName: 2.0
"""

MANIFEST_NO_VERSION = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.demo"
    android:compileSdkVersion="35">

    <uses-permission android:name="android.permission.INTERNET" />

    <application android:label="@string/app_name">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""


def test_load_manifest_facts_merges_apktool_yml(tmp_path: Path) -> None:
    from reverseapk_mcp.tools.decode import load_manifest_facts

    project = tmp_path / "apktool"
    project.mkdir()
    manifest_path = project / "AndroidManifest.xml"
    manifest_path.write_text(MANIFEST_NO_VERSION, encoding="utf-8")
    (project / "apktool.yml").write_text(APKTOOL_YML, encoding="utf-8")

    facts = load_manifest_facts(manifest_path)

    assert facts["min_sdk"] == 24
    assert facts["target_sdk"] == 35
    assert facts["version_code"] == 7
    assert facts["version_name"] == "2.0"
    assert facts["launchable_activity"] == "com.example.demo.MainActivity"
    assert facts["activities"][0]["full_name"] == "com.example.demo.MainActivity"


def test_restore_uses_sdk_inserted_once(tmp_path: Path) -> None:
    from reverseapk_mcp.tools.build import _restore_uses_sdk

    project = tmp_path / "apktool"
    project.mkdir()
    manifest_path = project / "AndroidManifest.xml"
    manifest_path.write_text(MANIFEST_NO_VERSION, encoding="utf-8")
    (project / "apktool.yml").write_text(APKTOOL_YML, encoding="utf-8")

    restored = _restore_uses_sdk(project)

    assert restored == {"min_sdk": 24, "target_sdk": 35}
    text = manifest_path.read_text(encoding="utf-8")
    assert '<uses-sdk android:minSdkVersion="24" android:targetSdkVersion="35" />' in text

    # Pemanggilan kedua tidak menambah elemen duplikat
    assert _restore_uses_sdk(project) is None
    assert text.count("<uses-sdk") == 1


def test_compare_fidelity_normalizes_relative_component_names() -> None:
    original = {
        "package": "com.example.demo",
        "version_name": "1.0",
        "min_sdk": 24,
        "target_sdk": 35,
        "permissions": ["android.permission.INTERNET"],
        "launchable_activity": ".MainActivity",
        "activities": [{"name": ".MainActivity"}],
        "services": [{"name": "SyncService"}],
        "receivers": [],
        "providers": [],
    }
    rebuilt = {
        "package": "com.example.demo",
        "version_name": "1.0",
        "min_sdk": 24,
        "target_sdk": 35,
        "permissions": ["android.permission.INTERNET"],
        "launchable_activity": "com.example.demo.MainActivity",
        "activities": [{"name": "com.example.demo.MainActivity"}],
        "services": [{"name": "com.example.demo.SyncService"}],
        "receivers": [],
        "providers": [],
    }

    report = reconstruct.compare_fidelity(original, rebuilt)
    assert report["score"] == 1.0

    component_check = next(item for item in report["checks"] if item["check"] == "components")
    assert component_check["ok"] is True
