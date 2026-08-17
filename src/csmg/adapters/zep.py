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

"""zep adapter — DEFERRED with evidence (KNOWN_ISSUES KI-2).

zep-python 2.0.2 read API is verified by signature (MemoryClient read
methods: list_sessions, search_sessions, get_session, get, get_fact...),
but functional verification requires a REMOTE endpoint + API key, which is
not available in this environment. Per the "never assume an adapter" rule,
reads raise AdapterError until an endpoint is configured; functional tests
belong behind @pytest.mark.slow with a configured endpoint.
"""

from __future__ import annotations

from csmg.adapters import AdapterError, register


class ZepAdapter:
    def __init__(self, api_url: str | None = None, api_key: str | None = None) -> None:
        if not api_url or not api_key:
            raise AdapterError(
                "zep adapter requires api_url + api_key; functional verification "
                "deferred (KNOWN_ISSUES KI-2)"
            )
        self._api_url = api_url
        self._api_key = api_key

    def list_chunks(self, principal: str | None = None) -> list[str]:
        raise AdapterError(
            "zep reads not yet implemented: requires configured endpoint "
            "(KNOWN_ISSUES KI-2); deferred, never assumed"
        )

    def get_chunk(self, chunk_id: str):
        raise AdapterError(
            "zep reads not yet implemented: requires configured endpoint "
            "(KNOWN_ISSUES KI-2); deferred, never assumed"
        )


register("zep", ZepAdapter)