"""CSMG-020: provenance resolver (AC3: never invents labels)."""

import dataclasses

import pytest

from csmg.provenance import resolve
from csmg.types import ChunkRead


def test_full_metadata_resolves_full_mode():
    c = ChunkRead(
        chunk_id="c1",
        content="x",
        metadata={
            "principal_id": "project-a",
            "session_id": "s1",
            "author": "agent",
            "ts": "2026-08-17",
            "scope": "project",
        },
    )
    p = resolve(c)
    assert p.mode == "full"
    assert p.attributable is True
    assert p.principal_id == "project-a"
    assert p.session_id == "s1"
    assert p.author == "agent"
    assert p.scope == "project"


def test_empty_metadata_is_poor():
    p = resolve(ChunkRead(chunk_id="c1", content="x"))
    assert p.mode == "poor"
    assert p.attributable is False
    assert p.principal_id is None


def test_partial_metadata_without_principal_is_poor():
    # session present but no principal => poor (the sensor never infers a
    # principal from a session id: that is KI-4's reasoned decision).
    c = ChunkRead(chunk_id="c1", content="x", metadata={"session_id": "manual-save"})
    p = resolve(c)
    assert p.mode == "poor"
    assert p.principal_id is None  # no invented "manual-save" label


def test_poor_mode_never_invents_placeholder():
    p = resolve(ChunkRead(chunk_id="c1", content="x"))
    # The only label the sensor may carry is a real one from the engine.
    assert p.principal_id is None or p.mode == "full"


def test_provenance_frozen():
    p = resolve(ChunkRead(chunk_id="c1", content="x"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.principal_id = "hacked"