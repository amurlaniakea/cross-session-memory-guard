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

"""CSMG-012: kill switch (kill.py). AC5 semantics."""

import pytest

from csmg.kill import is_disabled


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "On", " 1 "])
def test_disabled_truthy_values(monkeypatch, value):
    monkeypatch.setenv("CSMG_DISABLED", value)
    assert is_disabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "off", "disabled", "2"])
def test_disabled_falsy_values(monkeypatch, value):
    monkeypatch.setenv("CSMG_DISABLED", value)
    assert is_disabled() is False


def test_disabled_absent_env(monkeypatch):
    monkeypatch.delenv("CSMG_DISABLED", raising=False)
    assert is_disabled() is False