"""CSMG-040 core: run_audit over a leaky adapter (simulated T1) + fail-open."""

import json

from csmg.adapters import AdapterError
from csmg.events import JsonlEventSink
from csmg.scan import run_audit
from csmg.types import ChunkRead


class LeakyAdapter:
    """Simulates broken isolation (T1): alice's scan list includes b1,
    a chunk written by bob. a2 is near-identical to bob's b2 (similarity
    signal). Rehydrate writes come from list_principals (consistent engine
    view), so b1 has NO write record -> flowgraph stays unknown_chunk."""

    _content = {
        "a1": "Lorem ipsum dolor sit amet alice secret note",
        "a2": "quarterly budget report for project gamma 2026",
        "b1": "Lorem ipsum dolor sit amet alice secret note",
        "b2": "quarterly budget report for project gamma 2026",
        "legacy": "old unattributed note from manual save",
    }
    _owner = {"a1": "alice", "a2": "alice", "b1": "bob", "b2": "bob"}

    def list_principals(self):
        return ["alice", "bob"]

    def list_chunks(self, principal=None):
        if principal == "alice":
            return ["a1", "a2", "b1"]  # T1: b1 leaks into alice's scan
        if principal == "bob":
            return ["b2"]
        return ["legacy"]

    def get_chunk(self, chunk_id):
        if chunk_id not in self._content:
            raise AdapterError("missing")
        owner = self._owner.get(chunk_id)
        return ChunkRead(
            chunk_id=chunk_id,
            content=self._content[chunk_id],
            metadata={"principal_id": owner, "scope": "project"},
        )


def test_scan_detects_cross_read_and_similarity(tmp_path):
    sink = JsonlEventSink(directory=str(tmp_path))
    res = run_audit(LeakyAdapter(), "alice", sink=sink)
    assert res.scanned == 3  # a1, a2, b1
    assert res.emitted == 2  # b1 (mismatch) + a2 (similarity)
    assert res.by_signal["mismatch"] == 1
    assert res.by_signal["similarity"] == 1
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        ev = json.loads(line)
        assert "content" not in ev  # AC6
        assert set(ev["evidence"]) <= {"hash", "span"}
        assert ev["requester"] == "alice"


def test_scan_unattributed_chunk_is_inapplicable_not_suspicious(tmp_path):
    # Provenance-poor chunk in the scan: mismatch reports no_origin (not
    # fired), flowgraph unknown_chunk (not fired) — KI-4/KI-8 policy.
    class PoorAdapter(LeakyAdapter):
        def list_chunks(self, principal=None):
            return ["legacy"] if principal == "alice" else super().list_chunks(principal)

        def get_chunk(self, chunk_id):
            if chunk_id == "legacy":
                return ChunkRead(chunk_id="legacy", content="x", metadata={})
            return super().get_chunk(chunk_id)

    sink = JsonlEventSink(directory=str(tmp_path))
    res = run_audit(PoorAdapter(), "alice", sink=sink)
    assert res.scanned == 1
    assert res.emitted == 0  # provenance-poor => declared inapplicable
    assert res.by_signal == {}


def test_scan_fail_open_on_broken_adapter(tmp_path):
    class BrokenAdapter(LeakyAdapter):
        def get_chunk(self, chunk_id):
            raise AdapterError("store exploded")

    sink = JsonlEventSink(directory=str(tmp_path))
    res = run_audit(BrokenAdapter(), "alice", sink=sink)
    assert res.scanned == 0
    assert res.degraded == 3  # every chunk degradedly skipped, no crash (AC5)
    assert res.emitted == 0


def test_scan_shared_scopes_exempt_mismatch(tmp_path):
    class SharedAdapter(LeakyAdapter):
        def get_chunk(self, chunk_id):
            c = super().get_chunk(chunk_id)
            return ChunkRead(chunk_id=c.chunk_id, content=c.content,
                             metadata={"principal_id": c.metadata["principal_id"],
                                       "scope": "shared"})

    sink = JsonlEventSink(directory=str(tmp_path))
    res = run_audit(SharedAdapter(), "alice", shared_scopes={"shared"}, sink=sink)
    # b1 no longer fires mismatch (shared scope); similarity still fires on a2
    assert "mismatch" not in res.by_signal  # 0 fires -> key absent (>=1 semantics)
    assert res.by_signal["similarity"] == 1
    assert res.emitted == 1