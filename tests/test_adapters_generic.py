"""CSMG-032: generic JSONL + SQLite adapters."""

import json
import sqlite3

import pytest

from csmg.adapters import AdapterError
from csmg.adapters.jsonl_sqlite import JsonlAdapter, SqliteGenericAdapter


def _jsonl(tmp_path) -> str:
    p = tmp_path / "mem.jsonl"
    p.write_text(
        json.dumps({"id": "j1", "content": "hello", "metadata": {"principal_id": "p1"}})
        + "\n"
        + json.dumps({"id": "j2", "content": "world"})
        + "\n",
        encoding="utf-8",
    )
    return str(p)


def test_jsonl_list_and_get(tmp_path):
    a = JsonlAdapter(_jsonl(tmp_path))
    assert a.list_chunks("p1") == ["j1"]
    assert sorted(a.list_chunks(None)) == ["j1", "j2"]
    assert a.get_chunk("j2").metadata == {}
    with pytest.raises(AdapterError):
        a.get_chunk("nope")


def _sqlite(tmp_path, with_principal=True) -> str:
    db = str(tmp_path / "g.db")
    con = sqlite3.connect(db)
    if with_principal:
        con.execute("CREATE TABLE mem (id INTEGER PRIMARY KEY, content TEXT, principal_id TEXT)")
        con.execute("INSERT INTO mem VALUES (1, 'aaa', 'p1')")
        con.execute("INSERT INTO mem VALUES (2, 'bbb', 'p2')")
    else:
        con.execute("CREATE TABLE mem (id INTEGER PRIMARY KEY, content TEXT)")
        con.execute("INSERT INTO mem VALUES (1, 'aaa')")
    con.commit()
    con.close()
    return db


def test_sqlite_adapter_with_principal_column(tmp_path):
    a = SqliteGenericAdapter(_sqlite(tmp_path), "mem")
    assert a.list_chunks("p1") == ["1"]
    assert a.list_chunks(None) == ["1", "2"]
    chunk = a.get_chunk("2")
    assert chunk.metadata["principal_id"] == "p2"


def test_sqlite_adapter_without_principal_column(tmp_path):
    a = SqliteGenericAdapter(_sqlite(tmp_path, with_principal=False), "mem")
    assert a.list_chunks("p1") == []  # nothing attributable (never invents)
    assert a.list_chunks(None) == ["1"]
    assert "principal_id" not in a.get_chunk("1").metadata