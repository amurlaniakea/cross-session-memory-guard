"""Generic read-only adapters: JSONL and plain SQLite (SPEC §3.2).

Both treat the backend as data, not code: files/tables are opened strictly
read-only and metadata columns are optional (absent metadata -> the chunk
is exposed without principal labels, which the resolver reports as
provenance_mode="poor").
"""

from __future__ import annotations

import json
import sqlite3

from csmg.adapters import AdapterError, register
from csmg.types import ChunkRead


class JsonlAdapter:
    """Read-only JSONL adapter. Each line: {"id", "content", "metadata"?}."""

    def __init__(self, path: str) -> None:
        self._path = path

    def _records(self) -> list[dict]:
        try:
            with open(self._path, encoding="utf-8") as fh:
                return [json.loads(line) for line in fh if line.strip()]
        except (OSError, json.JSONDecodeError) as e:
            raise AdapterError(f"JsonlAdapter read failed: {e}") from e

    def list_chunks(self, principal: str | None = None) -> list[str]:
        out = []
        for rec in self._records():
            md = rec.get("metadata") or {}
            if principal is None or md.get("principal_id") == principal:
                out.append(str(rec["id"]))
        return out

    def list_principals(self) -> list[str]:
        seen: list[str] = []
        for rec in self._records():
            pid = (rec.get("metadata") or {}).get("principal_id")
            if pid and pid not in seen:
                seen.append(pid)
        return seen

    def get_chunk(self, chunk_id: str) -> ChunkRead:
        for rec in self._records():
            if str(rec["id"]) == str(chunk_id):
                return ChunkRead(
                    chunk_id=str(rec["id"]),
                    content=rec.get("content", ""),
                    metadata=rec.get("metadata") or {},
                )
        raise AdapterError(f"JsonlAdapter chunk not found: {chunk_id}")


class SqliteGenericAdapter:
    """Read-only adapter over an arbitrary SQLite table.

    Required columns: id, content. Optional metadata columns are detected
    via PRAGMA table_info and mapped to ChunkRead.metadata when present:
    principal_id, session_id, scope, ts.
    """

    def __init__(self, db_path: str, table: str) -> None:
        self._db = db_path
        self._table = table

    def _connect(self) -> sqlite3.Connection:
        try:
            con = sqlite3.connect(f"file:{self._db}?mode=ro", uri=True, timeout=10)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA query_only=ON")
            return con
        except sqlite3.Error as e:
            raise AdapterError(f"cannot open SQLite read-only: {e}") from e

    def _meta_cols(self, con: sqlite3.Connection) -> set:
        cols = {r["name"] for r in con.execute(f'PRAGMA table_info("{self._table}")')}
        return cols & {"principal_id", "session_id", "scope", "ts"}

    def list_chunks(self, principal: str | None = None) -> list[str]:
        con = self._connect()
        try:
            cols = self._meta_cols(con)
            if principal is None:
                rows = con.execute(
                    f'SELECT id FROM "{self._table}" ORDER BY id'
                ).fetchall()
            elif "principal_id" in cols:
                rows = con.execute(
                    f'SELECT id FROM "{self._table}" WHERE principal_id = ? ORDER BY id',
                    (principal,),
                ).fetchall()
            else:
                # no principal column -> nothing can be attributed to a tenant
                return []
            return [str(r["id"]) for r in rows]
        except sqlite3.Error as e:
            raise AdapterError(f"SqliteGenericAdapter list failed: {e}") from e
        finally:
            con.close()

    def list_principals(self) -> list[str]:
        con = self._connect()
        try:
            if "principal_id" not in self._meta_cols(con):
                return []
            rows = con.execute(
                f'SELECT DISTINCT principal_id FROM "{self._table}"'
                " WHERE principal_id IS NOT NULL AND principal_id != ''"
            ).fetchall()
            return [r["principal_id"] for r in rows]
        except sqlite3.Error as e:
            raise AdapterError(f"SqliteGenericAdapter list_principals failed: {e}") from e
        finally:
            con.close()

    def get_chunk(self, chunk_id: str) -> ChunkRead:
        con = self._connect()
        try:
            cols = self._meta_cols(con)
            sel = ["id", "content"] + sorted(cols)
            row = con.execute(
                'SELECT {cols} FROM "{t}" WHERE id = ?'.format(cols=", ".join(sel), t=self._table),
                (int(chunk_id),),
            ).fetchone()
        except (sqlite3.Error, ValueError) as e:
            raise AdapterError(f"SqliteGenericAdapter get failed: {e}") from e
        finally:
            con.close()
        if row is None:
            raise AdapterError(f"SqliteGenericAdapter chunk not found: {chunk_id}")
        metadata = {c: row[c] for c in cols if row[c] is not None}
        return ChunkRead(chunk_id=str(row["id"]), content=row["content"], metadata=metadata)


register("jsonl", JsonlAdapter)
register("sqlite", SqliteGenericAdapter)