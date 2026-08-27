"""Run-mode definitions for E1/E2/E3 and the default rule-engine chain.

The experiment definitions freeze E1/E2/E3 as distinct modes:

- ``E1``: generic agent, no industry configuration.
- ``E2``: generic agent with industry configuration, but without the formal
  time-lock / evidence / Critic chain.
- ``E3``: full system with industry configuration, time lock, evidence chain,
  and Critic.
- ``rule-engine``: the existing deterministic default pipeline. This remains
  the default and is the only mode that may run without a model provider.
"""

from __future__ import annotations

from typing import Literal

RunMode = Literal["rule-engine", "E1", "E2", "E3"]

ALL_MODES: tuple[RunMode, ...] = ("rule-engine", "E1", "E2", "E3")
EXPERIMENT_MODES: frozenset[str] = frozenset({"E1", "E2", "E3"})


def normalize_mode(mode: str) -> RunMode:
    """Validate and return a canonical run mode string."""
    if mode not in ALL_MODES:
        raise ValueError(
            f"E500 module=orchestrator.modes: unknown mode {mode!r}; "
            f"expected one of {', '.join(ALL_MODES)}"
        )
    return mode  # type: ignore[return-value]
