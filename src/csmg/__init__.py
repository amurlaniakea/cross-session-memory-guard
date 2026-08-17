"""cross-session-memory-guard.

Read-only cross-principal memory exfiltration sensor for multi-tenant LLM
agents. Observes, compares and alerts — never blocks or modifies memory
(Constitution v0.1, §2).
"""

from csmg.types import SENSOR_VERSION

__version__ = SENSOR_VERSION
__all__ = ["__version__"]