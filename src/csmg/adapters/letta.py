"""letta adapter — DEFERRED with evidence (KNOWN_ISSUES KI-1).

letta 0.16.8 exists on PyPI but was NOT installed/verified in the B0 spike
(heavy dependency tree). Per the "never assume an adapter" rule, the adapter
refuses to construct until its API is verified by execution; it must never
be silently assumed.
"""

from __future__ import annotations

from csmg.adapters import AdapterError, register


class LettaAdapter:
    def __init__(self, *args, **kwargs) -> None:
        raise AdapterError(
            "letta adapter deferred: package not verified in B0 spike "
            "(KNOWN_ISSUES KI-1); install + verify read API before use"
        )


register("letta", LettaAdapter)