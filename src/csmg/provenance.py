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

"""Provenance resolution for memory chunks (SPEC §4, AC3).

Extracts origin labels from engine-provided metadata. When the engine does
not provide a principal label the sensor MUST NOT invent one (Constitution
§4): it degrades to provenance_mode="poor" and signals that depend on
attribution declare themselves inapplicable.
"""

from __future__ import annotations

from dataclasses import dataclass

from csmg.types import ChunkRead


@dataclass(frozen=True)
class Provenance:
    principal_id: str | None
    session_id: str | None
    author: str | None
    ts: str | None
    scope: str | None
    mode: str  # "full" | "poor"

    @property
    def attributable(self) -> bool:
        """True only when we have a real principal label (never invented)."""
        return self.mode == "full" and self.principal_id is not None


def resolve(chunk: ChunkRead) -> Provenance:
    """Extract provenance from a chunk's metadata.

    metadata keys read: principal_id, session_id, author, ts, scope. Any
    missing key stays None. mode="full" only when principal_id is present;
    otherwise "poor" (declared, never guessed).
    """
    md = chunk.metadata or {}
    principal = md.get("principal_id")
    mode = "full" if principal else "poor"
    return Provenance(
        principal_id=principal,
        session_id=md.get("session_id"),
        author=md.get("author"),
        ts=md.get("ts"),
        scope=md.get("scope"),
        mode=mode,
    )