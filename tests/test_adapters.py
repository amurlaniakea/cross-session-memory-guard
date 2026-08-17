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

"""CSMG-030: ReadPort registry + CSMG-034: safe_call fail-open (AC5)."""

import pytest

from csmg.adapters import AdapterError, available, get_adapter, safe_call
from csmg.adapters.engram import EngramAdapter


def test_registry_available_includes_known_adapters():
    names = available()
    assert {"engram", "jsonl", "sqlite", "mem0", "langmem", "zep", "letta"} <= set(names)


def test_get_adapter_unknown_raises():
    with pytest.raises(AdapterError):
        get_adapter("no-such-backend")


def test_get_adapter_engram_constructs():
    a = get_adapter("engram")
    assert isinstance(a, EngramAdapter)


def test_safe_call_healthy_returns_result():
    assert safe_call("t", lambda x: x * 2, 21) == 42


def test_safe_call_adapter_error_returns_none():
    def boom():
        raise AdapterError("store down")

    assert safe_call("broken", boom) is None


def test_safe_call_generic_exception_returns_none():
    def boom():
        raise ValueError("unexpected")

    assert safe_call("broken", boom) is None  # fail-open, never propagates (AC5)