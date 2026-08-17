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

"""Kill switch (Constitution §2.2 / SPEC AC5).

CSMG_DISABLED=1|true|yes|on  -> total pass-through (zero observation,
zero latency). Any other value or absence -> sensor active.
"""

from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def is_disabled() -> bool:
    """True when the kill switch demands total pass-through."""
    return os.environ.get("CSMG_DISABLED", "").strip().lower() in _TRUTHY