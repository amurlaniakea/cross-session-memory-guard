"""Signal (a): origin-label mismatch vs requesting principal (deterministic).

Fires when the chunk's attributed principal differs from the requester AND
the chunk's scope is not an authorized shared scope. Without attribution
(provenance-poor) the signal is INAPPLICABLE and reports so (AC3) — it never
guesses a principal (Constitution §4).
"""

from __future__ import annotations

from csmg.provenance import Provenance
from csmg.types import SignalVerdict


def evaluate(
    origin: Provenance,
    requester: str,
    shared_scopes: set[str] | None = None,
) -> SignalVerdict:
    shared = shared_scopes or set()
    if not origin.attributable:
        return SignalVerdict(
            signal="mismatch",
            fired=False,
            confidence=1.0,
            detail={"reason": "no_origin"},
        )
    if origin.principal_id == requester:
        return SignalVerdict(
            signal="mismatch",
            fired=False,
            confidence=1.0,
            detail={"reason": "same_principal"},
        )
    if origin.scope and origin.scope in shared:
        return SignalVerdict(
            signal="mismatch",
            fired=False,
            confidence=1.0,
            detail={"reason": "shared_scope", "scope": origin.scope},
        )
    return SignalVerdict(
        signal="mismatch",
        fired=True,
        confidence=1.0,
        detail={"reason": "cross_principal"},
    )