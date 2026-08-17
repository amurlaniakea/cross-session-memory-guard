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

"""CSMG-033: deferred adapters (letta/zep) + mem0/langmem with fakes."""

import pytest

from csmg.adapters import AdapterError
from csmg.adapters.letta import LettaAdapter
from csmg.adapters.zep import ZepAdapter


def test_letta_adapter_refuses_construction():
    # KI-1: never assumed — the adapter refuses to exist until verified.
    with pytest.raises(AdapterError):
        LettaAdapter()


def test_zep_adapter_requires_endpoint_config():
    # KI-2: functional verification deferred; reads must not happen unverified.
    with pytest.raises(AdapterError):
        ZepAdapter()
    with pytest.raises(AdapterError):
        ZepAdapter(api_url="https://zep.example", api_key=None)


class FakeMemory:
    """Fake mirroring the mem0.Memory read API shape (ver. 2.0.18)."""

    def __init__(self, entries):
        self._entries = entries

    def get_all(self, filters=None, top_k=20):
        if filters and filters.get("user_id"):
            return [e for e in self._entries if e.get("user_id") == filters["user_id"]]
        return self._entries

    def get(self, memory_id):
        for e in self._entries:
            if str(e.get("id")) == str(memory_id):
                return e
        return None


def test_mem0_adapter_reads_with_fake(tmp_path):
    from csmg.adapters.mem0 import Mem0Adapter

    fake = FakeMemory(
        [
            {"id": "m1", "text": "alpha data", "user_id": "u1"},
            {"id": "m2", "text": "beta data", "user_id": "u2"},
        ]
    )
    a = Mem0Adapter(fake)
    assert a.list_chunks("u1") == ["m1"]
    assert sorted(a.list_chunks(None)) == ["m1", "m2"]
    chunk = a.get_chunk("m1")
    assert chunk.metadata["principal_id"] == "u1"
    with pytest.raises(AdapterError):
        a.get_chunk("missing")


def test_mem0_adapter_unexpected_shape_raises():
    from csmg.adapters.mem0 import Mem0Adapter

    class WeirdMemory:
        def get(self, memory_id):
            return {"no_text_here": 1}

        def get_all(self, filters=None, top_k=20):
            return [{"nope": True}]

    a = Mem0Adapter(WeirdMemory())
    with pytest.raises(AdapterError):  # never guess the shape
        a.get_chunk("m1")


class FakeStore:
    """Fake mirroring langgraph BaseStore read API (get/search)."""

    def __init__(self, items):
        self._items = items  # {(namespace, key): {"value": {...}}}

    def search(self, namespace_prefix, limit=10, **kw):
        return [
            _Item(key=k, value=v.get("value", {}))
            for (ns, k), v in self._items.items()
            if ns[: len(namespace_prefix)] == namespace_prefix
        ][:limit]

    def get(self, namespace, key, **kw):
        return self._items.get((namespace, key))


class _Item:
    def __init__(self, key, value):
        self.key = key
        self.value = value


def test_langmem_adapter_reads_with_fake():
    from csmg.adapters.langmem import LangMemAdapter

    store = FakeStore(
        {
            (("memories", "u1"), "k1"): {"value": {"content": "alpha"}},
            (("memories", "u2"), "k2"): {"value": {"content": "beta"}},
        }
    )
    a = LangMemAdapter(store)
    assert a.list_chunks("u1") == ["k1"]
    assert set(a.list_chunks(None)) == {"k1", "k2"}
    chunk = a.get_chunk("k1")
    assert chunk.content == "alpha"
    with pytest.raises(AdapterError):
        a.get_chunk("ghost")