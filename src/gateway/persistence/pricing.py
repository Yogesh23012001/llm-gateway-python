"""Per-model pricing and cost calculation. Prices in USD per million tokens.

Keep this current with vendor pricing pages. Stale pricing = wrong cost
tracking, which defeats the purpose. Treat updates as operational events.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float   # USD per 1M input tokens
    output_per_mtok: float  # USD per 1M output tokens


# Keyed by the RESOLVED model id (what the provider actually called),
# not the friendly name — so cost is accurate even if friendly names alias.
_PRICING: dict[str, ModelPricing] = {
    "claude-haiku-4-5-20251001": ModelPricing(input_per_mtok=0.80, output_per_mtok=4.00),
    "claude-sonnet-4-5": ModelPricing(input_per_mtok=3.00, output_per_mtok=15.00),
    "gemini-2.5-flash": ModelPricing(input_per_mtok=0.30, output_per_mtok=2.50),
    "gemini-2.0-flash": ModelPricing(input_per_mtok=0.10, output_per_mtok=0.40),
}

# Fallback for unknown models — log at 0 cost but don't crash.
_UNKNOWN = ModelPricing(input_per_mtok=0.0, output_per_mtok=0.0)


def calculate_cost_usd(*, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = _PRICING.get(model, _UNKNOWN)
    cost = (
        prompt_tokens * pricing.input_per_mtok / 1_000_000
        + completion_tokens * pricing.output_per_mtok / 1_000_000
    )
    return round(cost, 8)


def is_known_model(model: str) -> bool:
    return model in _PRICING