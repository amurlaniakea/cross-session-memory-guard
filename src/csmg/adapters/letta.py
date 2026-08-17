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

"""letta adapter — DEFERRED with evidence (KNOWN_ISSUES KI-1).

letta 0.16.8 exists on PyPI but was NOT installed/verified in the B0 spike
(heavy dependency tree). Per the "never assume an adapter" rule, the adapter
refuses to construct until its API is verified by execution; it must never
be silently assumed.
"""

from __future__ import annotations

from csmg.adapters import AdapterError, register


class LettaAdapter:
    def __init__(self, *args, **kwargs) -> None:
        raise AdapterError(
            "letta adapter deferred: package not verified in B0 spike "
            "(KNOWN_ISSUES KI-1); install + verify read API before use"
        )


register("letta", LettaAdapter)