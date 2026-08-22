"""Interface for cost/latency-aware provider selection under normal operation.

This is separate from the circuit-breaker/fallback path (which only kicks in
on *failure*). ScoringStrategy is what the router should consult when every
provider is healthy, to pick the best one to route *to* — not just which one
to avoid.

Everything in this file is a TODO for you (see docs/stages/phase4-generation.md) —
the shapes below are fixed so the router can be written against them, but no
actual scoring math lives here yet.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderStats:
    """Rolling stats the router tracks per provider, fed into scoring.

    TODO (you): decide how `recent_latency_ms` gets updated — e.g. an
    exponential moving average over each call's measured latency, a
    fixed-size rolling window, or something else. This class is just the
    shape a ScoringStrategy reads from; populating/updating it is part of
    the router logic you're writing.
    """

    provider_name: str
    recent_latency_ms: float
    cost_per_1k_tokens: float


class ScoringStrategy(Protocol):
    """A function that scores one provider for selection — higher is better.

    TODO (you): implement a scoring function matching this shape (a simple
    weighted combination of recent_latency_ms and cost_per_1k_tokens is
    plenty — this doesn't need to be sophisticated) and wire it into the
    router's provider-selection step for the normal-operation path.
    """

    def __call__(self, stats: ProviderStats) -> float: ...
