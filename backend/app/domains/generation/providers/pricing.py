"""Rough, illustrative per-provider cost estimates.

These are not billed anywhere and aren't kept in sync with live provider
pricing — they exist purely as a number the router's scoring strategy can
weigh against latency when picking a provider under normal operation.
Update them if you want more realistic figures; precision doesn't matter,
relative ordering (local free, hosted APIs cost something) does.
"""

ESTIMATED_COST_PER_1K_TOKENS: dict[str, float] = {
    "openai": 0.03,
    "anthropic": 0.03,
    "ollama": 0.0,  # local inference — no per-token API cost
    "mock": 0.0,
}


def estimated_cost_per_1k_tokens(provider_name: str) -> float:
    return ESTIMATED_COST_PER_1K_TOKENS.get(provider_name, 0.0)
