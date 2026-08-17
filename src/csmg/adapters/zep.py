"""zep adapter — DEFERRED with evidence (KNOWN_ISSUES KI-2).

zep-python 2.0.2 read API is verified by signature (MemoryClient read
methods: list_sessions, search_sessions, get_session, get, get_fact...),
but functional verification requires a REMOTE endpoint + API key, which is
not available in this environment. Per the "never assume an adapter" rule,
reads raise AdapterError until an endpoint is configured; functional tests
belong behind @pytest.mark.slow with a configured endpoint.
"""

from __future__ import annotations

from csmg.adapters import AdapterError, register


class ZepAdapter:
    def __init__(self, api_url: str | None = None, api_key: str | None = None) -> None:
        if not api_url or not api_key:
            raise AdapterError(
                "zep adapter requires api_url + api_key; functional verification "
                "deferred (KNOWN_ISSUES KI-2)"
            )
        self._api_url = api_url
        self._api_key = api_key

    def list_chunks(self, principal: str | None = None) -> list[str]:
        raise AdapterError(
            "zep reads not yet implemented: requires configured endpoint "
            "(KNOWN_ISSUES KI-2); deferred, never assumed"
        )

    def get_chunk(self, chunk_id: str):
        raise AdapterError(
            "zep reads not yet implemented: requires configured endpoint "
            "(KNOWN_ISSUES KI-2); deferred, never assumed"
        )


register("zep", ZepAdapter)