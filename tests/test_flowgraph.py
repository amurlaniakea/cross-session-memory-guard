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

"""CSMG-023: flowgraph signal (c)."""

from csmg.signals.flowgraph import FlowGraph


def test_authorized_read_not_fired():
    g = FlowGraph()
    g.record_write("project-a", "c1")
    v = g.record_read("c1", reader="project-b", authorized=True)
    assert v.fired is False
    assert v.detail["reason"] == "authorized"


def test_cross_boundary_read_fires():
    g = FlowGraph()
    g.record_write("project-a", "c1")
    v = g.record_read("c1", reader="project-b", authorized=False)
    assert v.fired is True
    assert v.detail["reason"] == "cross_boundary"
    assert v.detail["writer"] == "project-a"
    assert v.detail["reader"] == "project-b"


def test_same_principal_read_not_fired():
    g = FlowGraph()
    g.record_write("project-a", "c1")
    v = g.record_read("c1", reader="project-a", authorized=False)
    assert v.fired is False
    assert v.detail["reason"] == "authorized"


def test_unknown_chunk_not_fired_with_reason():
    g = FlowGraph()
    v = g.record_read("ghost-chunk", reader="project-b", authorized=False)
    assert v.fired is False
    assert v.detail["reason"] == "unknown_chunk"


def test_read_counter_tracks_multiple_reads():
    g = FlowGraph()
    g.record_write("project-a", "c1")
    g.record_read("c1", reader="project-a", authorized=False)
    g.record_read("c1", reader="project-a", authorized=False)
    assert g._reads["c1"] == 2


def test_rehydrate_primes_writes_from_engine_metadata():
    # KI-8 route 1: writes come from engine metadata, not sensor history.
    g = FlowGraph()
    loaded = g.rehydrate([("c1", "project-a"), ("c2", "project-b")])
    assert loaded == 2
    v = g.record_read("c1", reader="project-b", authorized=False)
    assert v.fired is True  # writer attribution survives a fresh graph
    assert v.detail["writer"] == "project-a"


def test_rehydrate_skips_unattributed_writers():
    # KI-8 contract (auditor finding): unattributed chunks are NOT recorded
    # as writes; reads of them stay unknown_chunk and NEVER fire
    # cross_boundary with writer=None (the 69% provenance-poor bucket must
    # be inapplicable, not suspicious by default — KI-4).
    g = FlowGraph()
    loaded = g.rehydrate([("c1", "project-a"), ("legacy1", None), ("legacy2", "")])
    assert loaded == 1  # only the attributed pair is recorded
    assert "legacy1" not in g._writes
    assert "legacy2" not in g._writes
    v = g.record_read("legacy1", reader="project-b", authorized=False)
    assert v.fired is False
    assert v.detail["reason"] == "unknown_chunk"


def test_record_write_ignores_empty_principal():
    g = FlowGraph()
    g.record_write(None, "ghost")
    v = g.record_read("ghost", reader="project-b", authorized=False)
    assert v.fired is False
    assert v.detail["reason"] == "unknown_chunk"