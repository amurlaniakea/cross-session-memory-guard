"""Kill switch (Constitution §2.2 / SPEC AC5).

CSMG_DISABLED=1|true|yes|on  -> total pass-through (zero observation,
zero latency). Any other value or absence -> sensor active.
"""

from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "on"}


def is_disabled() -> bool:
    """True when the kill switch demands total pass-through."""
    return os.environ.get("CSMG_DISABLED", "").strip().lower() in _TRUTHY