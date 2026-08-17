"""Engram adapter — THIN READ-ONLY DRIVER (scope clarification, 2026-08-17).

This adapter does NOT vendor nor include any Engram code. It is a thin,
read-only driver against a local Engram SQLite database (default
/home/sil/.engram/engram.db) used for dogfooding/tests in this environment.
Engram is treated exactly like any other backend (mem0, Letta, Zep,
JSONL/SQLite): observed through the same ReadPort contract, never modified,
never shipped as part of this repository's code. The DB is a local DATA
dependency for testing, not a library dependency.
"""

from __future__ import annotations

import sqlite3

from csmg.adapters import AdapterError, register
from csmg.types import ChunkRead

_METADATA_COLS = ("session_id", "type", "title", "project", "scope", "created_at")


class EngramAdapter:
    """Read-only access to an Engram DB (observations table).

    KI-4 mapping (resolved 2026-08-17): principal := project when non-empty.
    Observations with empty project (legacy 'manual-save' bucket) carry NO
    principal label: get_chunk omits principal_id -> the provenance resolver
    reports provenance_mode="poor" (signal (a) inapplicable, declared).
    """

    def __init__(self, db_path: str = "/home/sil/.engram/engram.db") -> None:
        self._db = db_path

    def _connect(self) -> sqlite3.Connection:
        try:
            con = sqlite3.connect(f"file:{self._db}?mode=ro", uri=True, timeout=10)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA query_only=ON")
            return con
        except sqlite3.Error as e:
            raise AdapterError(f"cannot open Engram DB read-only: {e}") from e

    def list_chunks(self, principal: str | None = None) -> list[str]:
        con = self._connect()
        try:
            if principal is None:
                # unattributed bucket: legacy rows without a project label
                rows = con.execute(
                    "SELECT id FROM observations WHERE (project IS NULL OR project = '')"
                    " AND deleted_at IS NULL ORDER BY id"
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT id FROM observations WHERE project = ? AND deleted_at IS NULL"
                    " ORDER BY id",
                    (principal,),
                ).fetchall()
            return [str(r["id"]) for r in rows]
        except sqlite3.Error as e:
            raise AdapterError(f"Engram list_chunks failed: {e}") from e
        finally:
            con.close()

    def get_chunk(self, chunk_id: str) -> ChunkRead:
        con = self._connect()
        try:
            row = con.execute(
                "SELECT id, {cols}, content FROM observations"
                " WHERE id = ? AND deleted_at IS NULL".format(
                    cols=", ".join(_METADATA_COLS)
                ),
                (int(chunk_id),),
            ).fetchone()
        except (sqlite3.Error, ValueError) as e:
            raise AdapterError(f"Engram get_chunk failed for {chunk_id}: {e}") from e
        finally:
            con.close()
        if row is None:
            raise AdapterError(f"Engram chunk not found (or deleted): {chunk_id}")
        metadata = {
            "session_id": row["session_id"],
            "type": row["type"],
            "scope": row["scope"],
            "ts": row["created_at"],
        }
        if row["project"]:
            metadata["principal_id"] = row["project"]
        return ChunkRead(chunk_id=str(row["id"]), content=row["content"], metadata=metadata)


register("engram", EngramAdapter)