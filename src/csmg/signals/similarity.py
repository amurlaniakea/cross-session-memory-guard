"""Signal (b): suspicious content similarity (heuristic, no models).

Baseline: 4-gram shingle Jaccard + optional simhash (stdlib only). The
`embed` extra will swap in cosine similarity through the same interface.
The verdict detail NEVER includes matched content (AC6) — only the score
and the threshold used.
"""

from __future__ import annotations

import hashlib

from csmg.types import SignalVerdict

_SHINGLE_SIZE = 4
DEFAULT_THRESHOLD = 0.75


def shingles(text: str, k: int = _SHINGLE_SIZE) -> set:
    text = text.strip()
    if not text:
        return set()
    if len(text) < k:
        return {text}
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def jaccard(a: set, b: set) -> float:
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


def simhash(text: str, k: int = _SHINGLE_SIZE) -> int:
    """64-bit simhash over shingles (deterministic across processes)."""
    acc = 0
    for sg in shingles(text, k):
        h = int.from_bytes(hashlib.sha1(sg.encode("utf-8")).digest()[:8], "big")
        acc ^= h
    return acc


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def evaluate(
    candidate: str,
    reference: str,
    threshold: float = DEFAULT_THRESHOLD,
) -> SignalVerdict:
    score = jaccard(shingles(candidate), shingles(reference))
    return SignalVerdict(
        signal="similarity",
        fired=score >= threshold,
        confidence=score,  # heuristic: raw similarity as confidence
        detail={"similarity": score, "threshold": threshold},
    )