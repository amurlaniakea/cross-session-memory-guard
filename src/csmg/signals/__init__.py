"""Detection signals (SPEC §3).

(a) mismatch    — origin label vs requesting principal (deterministic)
(b) similarity  — suspicious content similarity (heuristic, no models)
(c) flowgraph   — who-wrote -> who-read flow (heuristic)
"""

from csmg.signals.flowgraph import FlowGraph
from csmg.signals.mismatch import evaluate as evaluate_mismatch
from csmg.signals.similarity import evaluate as evaluate_similarity
from csmg.signals.similarity import hamming, jaccard, shingles, simhash

__all__ = [
    "FlowGraph",
    "evaluate_mismatch",
    "evaluate_similarity",
    "hamming",
    "jaccard",
    "shingles",
    "simhash",
]