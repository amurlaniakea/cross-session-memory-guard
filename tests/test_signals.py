"""CSMG-021 (mismatch) + CSMG-022 (similarity): signal unit tests."""


from csmg.provenance import resolve
from csmg.signals import evaluate_mismatch, evaluate_similarity
from csmg.signals.similarity import jaccard, shingles
from csmg.types import ChunkRead


def _origin(principal="project-a", scope="project"):
    return resolve(
        ChunkRead(
            chunk_id="c1",
            content="x",
            metadata={"principal_id": principal, "scope": scope},
        )
    )


# ---- mismatch (a) ----

def test_mismatch_fires_on_cross_principal():
    v = evaluate_mismatch(_origin("project-a"), requester="project-b")
    assert v.signal == "mismatch"
    assert v.fired is True
    assert v.confidence == 1.0
    assert v.detail["reason"] == "cross_principal"


def test_mismatch_not_fired_same_principal():
    v = evaluate_mismatch(_origin("project-a"), requester="project-a")
    assert v.fired is False
    assert v.detail["reason"] == "same_principal"


def test_mismatch_not_fired_shared_scope():
    v = evaluate_mismatch(
        _origin("project-a", scope="shared"), requester="project-b",
        shared_scopes={"shared"},
    )
    assert v.fired is False
    assert v.detail["reason"] == "shared_scope"


def test_mismatch_inapplicable_without_origin_ac3():
    poor = resolve(ChunkRead(chunk_id="c1", content="x"))
    v = evaluate_mismatch(poor, requester="project-b")
    assert v.fired is False
    assert v.detail["reason"] == "no_origin"  # declared, not guessed


def test_mismatch_fires_when_scope_unknown_and_not_shared():
    v = evaluate_mismatch(_origin("project-a", scope=None), requester="project-b")
    assert v.fired is True


# ---- similarity (b) ----

def test_shingles_and_jaccard_basics():
    a = shingles("the quick brown fox")
    b = shingles("the quick brown fox")
    assert a == b
    assert jaccard(a, b) == 1.0
    assert jaccard(a, shingles("zzz qqq aaa")) == 0.0
    assert jaccard(set(), set()) == 0.0  # empty vs empty -> 0 (no signal)


def test_similarity_identical_fires():
    v = evaluate_similarity("pedro work in madrid", "pedro work in madrid")
    assert v.fired is True
    assert v.confidence == 1.0
    assert set(v.detail) == {"similarity", "threshold"}  # no content keys (AC6)


def test_similarity_disjoint_not_fired():
    v = evaluate_similarity("one two three", "alpha beta gamma")
    assert v.fired is False
    assert v.detail["similarity"] == 0.0


def test_similarity_threshold_configurable():
    low = evaluate_similarity("same base text A", "same base text B", threshold=0.3)
    high = evaluate_similarity("same base text A", "same base text B", threshold=0.999)
    assert low.fired is True
    assert high.fired is False


def test_similarity_verdict_never_contains_matched_text():
    v = evaluate_similarity("secret sentence xyz", "secret sentence xyz")
    # AC6: detail carries only numeric scores/threshold — no content strings.
    assert set(v.detail) == {"similarity", "threshold"}
    assert isinstance(v.detail["similarity"], float)
    assert isinstance(v.detail["threshold"], float)