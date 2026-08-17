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