# SPDX-FileCopyrightText: 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Copyright (C) 2026 Pedro Sordo Martínez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program. If not, see
# <https://www.gnu.org/licenses/>.

"""CSMG-031: Engram adapter — hermetic fixture + real-DB dogfooding (slow)."""

import os
import sqlite3

import pytest

from csmg.adapters import AdapterError
from csmg.adapters.engram import EngramAdapter

REAL_DB = "/home/sil/.engram/engram.db"


def _make_db(tmp_path) -> str:
    db = str(tmp_path / "engram_t.db")
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE observations (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL,"
        " type TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, project TEXT,"
        " scope TEXT NOT NULL DEFAULT 'project', created_at TEXT NOT NULL,"
        " deleted_at TEXT)"
    )
    con.execute(
        "INSERT INTO observations (id, session_id, type, title, content, project, created_at)"
        " VALUES (1, 's1', 'manual', 'T1', 'content alpha', 'alpha', '2026-01-01')"
    )
    con.execute(
        "INSERT INTO observations (id, session_id, type, title, content, project, created_at)"
        " VALUES (2, 'manual-save', 'manual', 'T2', 'content legacy', NULL, '2026-01-02')"
    )
    con.commit()
    con.close()
    return db


def test_list_chunks_by_principal(tmp_path):
    a = EngramAdapter(_make_db(tmp_path))
    assert a.list_chunks("alpha") == ["1"]
    assert a.list_chunks("other") == []


def test_list_chunks_unattributed_bucket(tmp_path):
    # KI-4: legacy rows without project are listed under principal=None
    a = EngramAdapter(_make_db(tmp_path))
    assert a.list_chunks(None) == ["2"]


def test_get_chunk_metadata_kI4_mapping(tmp_path):
    a = EngramAdapter(_make_db(tmp_path))
    chunk = a.get_chunk("1")
    assert chunk.chunk_id == "1"
    assert chunk.metadata["principal_id"] == "alpha"  # principal := project
    assert chunk.metadata["session_id"] == "s1"

    legacy = a.get_chunk("2")
    assert "principal_id" not in legacy.metadata  # no invented label (KI-4)


def test_get_chunk_missing_raises_adapter_error(tmp_path):
    a = EngramAdapter(_make_db(tmp_path))
    with pytest.raises(AdapterError):
        a.get_chunk("999")


def test_bad_db_path_raises_adapter_error(tmp_path):
    a = EngramAdapter(str(tmp_path / "no-such.db"))
    with pytest.raises(AdapterError):
        a.list_chunks("alpha")


def test_connection_is_readonly(tmp_path):
    a = EngramAdapter(_make_db(tmp_path))
    con = a._connect()
    with pytest.raises(sqlite3.OperationalError):
        con.execute(
            "INSERT INTO observations (session_id, type, title, content)"
            " VALUES ('x','y','z','w')"
        )
    con.close()


@pytest.mark.slow
def test_engram_real_db_dogfooding():
    if not os.path.exists(REAL_DB):
        pytest.skip("Engram DB not present in this environment")
    a = EngramAdapter(REAL_DB)
    # real dogfooding read against the local DB (project 'centinela' has 4 obs)
    ids = a.list_chunks("centinela")
    assert len(ids) >= 1
    chunk = a.get_chunk(ids[0])
    assert chunk.chunk_id == ids[0]