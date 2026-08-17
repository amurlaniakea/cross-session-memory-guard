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

"""Signal (a): origin-label mismatch vs requesting principal (deterministic).

Fires when the chunk's attributed principal differs from the requester AND
the chunk's scope is not an authorized shared scope. Without attribution
(provenance-poor) the signal is INAPPLICABLE and reports so (AC3) — it never
guesses a principal (Constitution §4).
"""

from __future__ import annotations

from csmg.provenance import Provenance
from csmg.types import SignalVerdict


def evaluate(
    origin: Provenance,
    requester: str,
    shared_scopes: set[str] | None = None,
) -> SignalVerdict:
    shared = shared_scopes or set()
    if not origin.attributable:
        return SignalVerdict(
            signal="mismatch",
            fired=False,
            confidence=1.0,
            detail={"reason": "no_origin"},
        )
    if origin.principal_id == requester:
        return SignalVerdict(
            signal="mismatch",
            fired=False,
            confidence=1.0,
            detail={"reason": "same_principal"},
        )
    if origin.scope and origin.scope in shared:
        return SignalVerdict(
            signal="mismatch",
            fired=False,
            confidence=1.0,
            detail={"reason": "shared_scope", "scope": origin.scope},
        )
    return SignalVerdict(
        signal="mismatch",
        fired=True,
        confidence=1.0,
        detail={"reason": "cross_principal"},
    )