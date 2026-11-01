"""Indexer kode berbasis SQLite FTS5.

Tujuan utama: agent bisa mencari kelas, method, field, dan string tanpa harus
membaca ribuan file hasil decompile.
"""

from __future__ import annotations

import bisect
import json
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MAX_FILE_BYTES = 2_000_000
MAX_SYMBOLS_PER_FILE = 1_500
SNIPPET_LIMIT = 240

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE NOT NULL,
        kind TEXT NOT NULL,
        language TEXT,
        bytes INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS symbols (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        name TEXT NOT NULL,
        parent TEXT,
        line INTEGER,
        snippet TEXT
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS symbol_fts USING fts5(
        name,
        parent,
        snippet,
        path UNINDEXED,
        kind UNINDEXED,
        line UNINDEXED,
        tokenize='unicode61'
    )
    """,
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)",
    "CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id)",
    "CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind)",
    "CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)",
)

JAVA_TYPE = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)")
JAVA_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
JAVA_METHOD = re.compile(
    r"^[ \t]*(?:(?:public|private|protected|static|final|abstract|synchronized|native|default|strictfp)\s+)*"
    r"[\w$<>\[\].,?\s]+\s+([A-Za-z_$][\w$]*)\s*\(",
    re.M,
)
JAVA_FIELD = re.compile(
    r"^[ \t]*(?:(?:public|private|protected|static|final|volatile|transient)\s+)+"
    r"[\w$<>\[\].,?]+\s+([A-Za-z_$][\w$]*)\s*(?:=|;)",
    re.M,
)
JAVA_STRING = re.compile(r'"([^"\\\n]{4,160})"')

SMALI_CLASS = re.compile(r"^\.class\s+.*?L([\w/$]+);", re.M)
SMALI_SUPER = re.compile(r"^\.super\s+L([\w/$]+);", re.M)
SMALI_METHOD = re.compile(r"^\.method\s+.*?\b([\w$<>]+)\(", re.M)
SMALI_FIELD = re.compile(r"^\.field\s+.*?\b([\w$]+):", re.M)
SMALI_STRING = re.compile(r'const-string(?:/jumbo)?\s+\w+,\s+"([^"]{4,200})"')

XML_RESOURCE = re.compile(r'<(string|bool|integer|color|dimen)\s+name="([^"]+)"[^>]*>([^<]{0,200})')

FTS_TOKEN = re.compile(r"[\w$./:-]+", re.UNICODE)


@dataclass(slots=True)
class IndexedFile:
    path: Path
    kind: str
    language: str


@dataclass(slots=True)
class Symbol:
    kind: str
    name: str
    parent: str = ""
    line: int = 0
    snippet: str = ""


@dataclass(slots=True)
class IndexStats:
    files: int = 0
    symbols: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    skipped_files: int = 0
    duration_s: float = 0.0
    db_path: str = ""
    fts_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "files": self.files,
            "symbols": self.symbols,
            "by_kind": self.by_kind,
            "skipped_files": self.skipped_files,
            "duration_s": self.duration_s,
            "db_path": self.db_path,
            "fts_enabled": self.fts_enabled,
        }


class _LineMap:
    """Pemetaan offset ke nomor baris berbasis bisect."""

    __slots__ = ("starts",)

    def __init__(self, text: str) -> None:
        self.starts = [0]
        self.starts.extend(match.end() for match in re.finditer("\n", text))

    def line_of(self, offset: int) -> int:
        return bisect.bisect_right(self.starts, offset)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _snippet(text: str, match_start: int) -> str:
    start = max(0, match_start - 40)
    return _clean(text[start : start + SNIPPET_LIMIT])


def _symbols_for_java(text: str, relative: str) -> list[Symbol]:
    line_map = _LineMap(text)
    package_match = JAVA_PACKAGE.search(text)
    package = package_match.group(1) if package_match else Path(relative).stem

    symbols: list[Symbol] = []
    for match in JAVA_TYPE.finditer(text):
        symbols.append(
            Symbol("class", match.group(1), package, line_map.line_of(match.start()), _snippet(text, match.start()))
        )
    for match in JAVA_METHOD.finditer(text):
        name = match.group(1)
        if name in {"if", "for", "while", "switch", "catch", "return", "new", "else"}:
            continue
        symbols.append(
            Symbol("method", name, package, line_map.line_of(match.start()), _snippet(text, match.start()))
        )
    for match in JAVA_FIELD.finditer(text):
        symbols.append(
            Symbol("field", match.group(1), package, line_map.line_of(match.start()), _snippet(text, match.start()))
        )
    for match in JAVA_STRING.finditer(text):
        symbols.append(
            Symbol("string", match.group(1), package, line_map.line_of(match.start()), "")
        )
        if len(symbols) >= MAX_SYMBOLS_PER_FILE:
            break
    return symbols[:MAX_SYMBOLS_PER_FILE]


def _symbols_for_smali(text: str, relative: str) -> list[Symbol]:
    line_map = _LineMap(text)
    class_match = SMALI_CLASS.search(text)
    parent = class_match.group(1).replace("/", ".") if class_match else Path(relative).stem

    symbols: list[Symbol] = []
    if class_match:
        symbols.append(
            Symbol("class", parent.rsplit(".", 1)[-1], parent, line_map.line_of(class_match.start()), "")
        )

    for match in SMALI_METHOD.finditer(text):
        symbols.append(
            Symbol("method", match.group(1), parent, line_map.line_of(match.start()), _snippet(text, match.start()))
        )
    for match in SMALI_FIELD.finditer(text):
        symbols.append(
            Symbol("field", match.group(1), parent, line_map.line_of(match.start()), _snippet(text, match.start()))
        )
    for match in SMALI_STRING.finditer(text):
        symbols.append(
            Symbol("string", match.group(1), parent, line_map.line_of(match.start()), "")
        )
        if len(symbols) >= MAX_SYMBOLS_PER_FILE:
            break
    return symbols[:MAX_SYMBOLS_PER_FILE]


def _symbols_for_xml(text: str, relative: str) -> list[Symbol]:
    line_map = _LineMap(text)
    symbols: list[Symbol] = []
    for match in XML_RESOURCE.finditer(text):
        symbols.append(
            Symbol(
                "resource",
                match.group(2),
                match.group(1),
                line_map.line_of(match.start()),
                _clean(match.group(3))[:SNIPPET_LIMIT],
            )
        )
    return symbols[:MAX_SYMBOLS_PER_FILE]


PARSERS = {
    "java": _symbols_for_java,
    "smali": _symbols_for_smali,
    "xml": _symbols_for_xml,
}


def _iter_files(roots: Iterable[tuple[Path, str, str]]) -> Iterable[IndexedFile]:
    for root, kind, language in roots:
        if not root.is_dir():
            continue
        if kind == "java":
            paths = root.rglob("*.java")
        elif kind == "smali":
            paths = root.rglob("*.smali")
        else:
            paths = root.glob("values*/*.xml")
        for path in paths:
            if path.is_file():
                yield IndexedFile(path=path, kind=kind, language=language)


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def _create_schema(connection: sqlite3.Connection) -> bool:
    fts_enabled = True
    for statement in SCHEMA_STATEMENTS:
        try:
            connection.execute(statement)
        except sqlite3.OperationalError as exc:
            if "fts5" in str(exc).lower():
                fts_enabled = False
                continue
            raise
    connection.commit()
    return fts_enabled


def build_index(
    db_path: Path,
    roots: Iterable[tuple[Path, str, str]],
    *,
    base_dir: Path | None = None,
    max_files: int = 0,
) -> IndexStats:
    """Bangun ulang index dari direktori hasil decode."""

    started = datetime.now(timezone.utc)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()

    stats = IndexStats(db_path=str(db_path))
    kind_counter: Counter[str] = Counter()

    connection = _connect(db_path)
    try:
        stats.fts_enabled = _create_schema(connection)
        cursor = connection.cursor()

        processed = 0
        for entry in _iter_files(roots):
            if max_files and processed >= max_files:
                break
            processed += 1

            try:
                if entry.path.stat().st_size > MAX_FILE_BYTES:
                    stats.skipped_files += 1
                    continue
                text = entry.path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                stats.skipped_files += 1
                continue

            relative = (
                entry.path.relative_to(base_dir).as_posix()
                if base_dir is not None
                else entry.path.name
            )
            parser = PARSERS.get(entry.language)
            symbols = parser(text, relative) if parser else []

            cursor.execute(
                "INSERT OR REPLACE INTO files(path, kind, language, bytes) VALUES (?, ?, ?, ?)",
                (relative, entry.kind, entry.language, len(text.encode("utf-8", errors="replace"))),
            )
            file_id = cursor.lastrowid

            if symbols:
                cursor.executemany(
                    "INSERT INTO symbols(file_id, kind, name, parent, line, snippet) VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (file_id, item.kind, item.name[:400], item.parent[:400], item.line, item.snippet)
                        for item in symbols
                    ],
                )
                if stats.fts_enabled:
                    cursor.execute(
                        """
                        INSERT INTO symbol_fts(rowid, name, parent, snippet, path, kind, line)
                        SELECT id, name, parent, snippet, ?, kind, line
                        FROM symbols WHERE file_id = ?
                        """,
                        (relative, file_id),
                    )

            stats.files += 1
            stats.symbols += len(symbols)
            for item in symbols:
                kind_counter[item.kind] += 1

        stats.by_kind = dict(kind_counter)
        stats.duration_s = round((datetime.now(timezone.utc) - started).total_seconds(), 2)

        cursor.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            [
                ("built_at", started.isoformat(timespec="seconds")),
                ("stats", json.dumps(stats.to_dict(), ensure_ascii=False)),
            ],
        )
        connection.commit()
        cursor.execute("ANALYZE")
        connection.commit()
    finally:
        connection.close()

    return stats


def _fts_query(query: str) -> str:
    tokens = [token for token in FTS_TOKEN.findall(query) if len(token) >= 2]
    return " AND ".join(f'"{token}"*' for token in tokens[:8])


def search(
    db_path: Path,
    query: str,
    *,
    kind: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Cari simbol dengan FTS5, fallback ke LIKE bila FTS tidak tersedia."""

    if not db_path.is_file() or not query.strip():
        return []

    safe_limit = max(1, min(int(limit), 200))
    safe_offset = max(0, int(offset))
    match = _fts_query(query)

    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        rows: list[sqlite3.Row] = []
        if match:
            try:
                sql = (
                    "SELECT path, kind, name, parent, line, snippet FROM symbol_fts "
                    "WHERE symbol_fts MATCH ?"
                )
                parameters: list[Any] = [match]
                if kind:
                    sql += " AND kind = ?"
                    parameters.append(kind)
                sql += " ORDER BY rank LIMIT ? OFFSET ?"
                parameters += [safe_limit, safe_offset]
                rows = list(connection.execute(sql, parameters))
            except sqlite3.OperationalError:
                rows = []

        if not rows:
            like = f"%{query.strip()}%"
            sql = (
                "SELECT f.path AS path, s.kind AS kind, s.name AS name, s.parent AS parent, "
                "s.line AS line, s.snippet AS snippet FROM symbols s "
                "JOIN files f ON f.id = s.file_id WHERE (s.name LIKE ? OR s.snippet LIKE ?)"
            )
            parameters = [like, like]
            if kind:
                sql += " AND s.kind = ?"
                parameters.append(kind)
            sql += " LIMIT ? OFFSET ?"
            parameters += [safe_limit, safe_offset]
            rows = list(connection.execute(sql, parameters))

        return [
            {
                "path": row["path"],
                "kind": row["kind"],
                "name": row["name"],
                "parent": row["parent"],
                "line": row["line"],
                "snippet": _clean(row["snippet"] or "")[:SNIPPET_LIMIT],
            }
            for row in rows
        ]
    finally:
        connection.close()


def references(db_path: Path, symbol: str, *, limit: int = 30) -> list[dict[str, Any]]:
    """Cari referensi simbol pada snippet dan nama."""

    return search(db_path, symbol, limit=limit)


def index_stats(db_path: Path) -> dict[str, Any]:
    if not db_path.is_file():
        return {"exists": False}

    connection = sqlite3.connect(str(db_path))
    try:
        files = connection.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        symbols = connection.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        by_kind = dict(connection.execute("SELECT kind, COUNT(*) FROM symbols GROUP BY kind"))
        meta_rows = dict(connection.execute("SELECT key, value FROM meta"))
    finally:
        connection.close()

    payload: dict[str, Any] = {
        "exists": True,
        "files": files,
        "symbols": symbols,
        "by_kind": by_kind,
    }
    if "built_at" in meta_rows:
        payload["built_at"] = meta_rows["built_at"]
    return payload


def read_slice(path: Path, start_line: int = 1, end_line: int = 200, *, max_lines: int = 400) -> dict[str, Any]:
    """Baca potongan file dengan batas jumlah baris."""

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    start = max(1, int(start_line))
    requested_end = max(start, int(end_line))
    end = min(requested_end, start + max_lines - 1, total)

    return {
        "path": str(path),
        "start_line": start,
        "end_line": end,
        "total_lines": total,
        "truncated": end < total or (requested_end - start + 1) > max_lines,
        "content": "\n".join(lines[start - 1 : end]) if total else "",
    }
