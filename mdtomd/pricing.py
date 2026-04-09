from __future__ import annotations

from dataclasses import dataclass

from .llm.providers import normalize_provider_name


@dataclass(frozen=True)
class ModelPrice:
    provider: str
    model: str
    currency: str
    input_per_million: float
    output_per_million: float
    input_cached_per_million: float | None = None
    source: str = ""
    note: str = ""


@dataclass(frozen=True)
class CostEstimate:
    input_cost: float
    output_cost_if_source_tokens_match: float
    total_cost_if_source_tokens_match: float


_PROVIDER_FALLBACKS = {
    "openai-codex": "openai",
    "gemini-openai": "gemini",
    "kimi-anthropic": "kimi",
    "minimax-anthropic": "minimax",
    "minimax-cn": "minimax",
    "alibaba": "qwen",
    "ai-gateway": "openai",
    "opencode-go": "zai",
}

_MODEL_ALIASES = {
    "claude-3-5-sonnet": "claude-3.5-sonnet",
    "claude-3-5-sonnet-latest": "claude-3.5-sonnet",
    "openai/gpt-4.1": "gpt-4.1",
    "openai/gpt-4.1-mini": "gpt-4.1-mini",
    "openai/gpt-4.1-nano": "gpt-4.1-nano",
    "openai/gpt-5.4": "gpt-5.4",
    "openai/gpt-5.4-mini": "gpt-5.4-mini",
    "openai/gpt-5.4-nano": "gpt-5.4-nano",
    "google/gemini-2.5-flash": "gemini-2.5-flash",
    "google/gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
    "google/gemini-2.5-flash-preview": "gemini-2.5-flash-preview-09-2025",
}

_PRICES: dict[tuple[str, str], ModelPrice] = {
    ("anthropic", "claude-3.5-sonnet"): ModelPrice(
        provider="anthropic",
        model="claude-3.5-sonnet",
        currency="USD",
        input_per_million=3.0,
        output_per_million=15.0,
        source="llm-prices:data/anthropic.json",
    ),
    ("openai", "gpt-4.1"): ModelPrice(
        provider="openai",
        model="gpt-4.1",
        currency="USD",
        input_per_million=2.0,
        output_per_million=8.0,
        input_cached_per_million=0.5,
        source="llm-prices:data/openai.json",
    ),
    ("openai", "gpt-4.1-mini"): ModelPrice(
        provider="openai",
        model="gpt-4.1-mini",
        currency="USD",
        input_per_million=0.4,
        output_per_million=1.6,
        input_cached_per_million=0.1,
        source="llm-prices:data/openai.json",
    ),
    ("openai", "gpt-4.1-nano"): ModelPrice(
        provider="openai",
        model="gpt-4.1-nano",
        currency="USD",
        input_per_million=0.1,
        output_per_million=0.4,
        input_cached_per_million=0.025,
        source="llm-prices:data/openai.json",
    ),
    ("openai", "gpt-5.4"): ModelPrice(
        provider="openai",
        model="gpt-5.4",
        currency="USD",
        input_per_million=2.5,
        output_per_million=15.0,
        input_cached_per_million=0.25,
        source="llm-prices:data/openai.json",
    ),
    ("openai", "gpt-5.4-mini"): ModelPrice(
        provider="openai",
        model="gpt-5.4-mini",
        currency="USD",
        input_per_million=0.75,
        output_per_million=4.5,
        input_cached_per_million=0.075,
        source="llm-prices:data/openai.json",
    ),
    ("openai", "gpt-5.4-nano"): ModelPrice(
        provider="openai",
        model="gpt-5.4-nano",
        currency="USD",
        input_per_million=0.2,
        output_per_million=1.25,
        input_cached_per_million=0.02,
        source="llm-prices:data/openai.json",
    ),
    ("deepseek", "deepseek-chat"): ModelPrice(
        provider="deepseek",
        model="deepseek-chat",
        currency="USD",
        input_per_million=0.27,
        output_per_million=1.1,
        source="llm-prices:data/deepseek.json",
    ),
    ("deepseek", "deepseek-reasoner"): ModelPrice(
        provider="deepseek",
        model="deepseek-reasoner",
        currency="USD",
        input_per_million=0.55,
        output_per_million=2.19,
        source="llm-prices:data/deepseek.json",
    ),
    ("gemini", "gemini-2.5-pro"): ModelPrice(
        provider="gemini",
        model="gemini-2.5-pro",
        currency="USD",
        input_per_million=1.25,
        output_per_million=10.0,
        input_cached_per_million=0.125,
        source="llm-prices:data/google.json",
    ),
    ("gemini", "gemini-2.5-flash"): ModelPrice(
        provider="gemini",
        model="gemini-2.5-flash",
        currency="USD",
        input_per_million=0.3,
        output_per_million=2.5,
        input_cached_per_million=0.03,
        source="llm-prices:data/google.json",
    ),
    ("gemini", "gemini-2.5-flash-lite"): ModelPrice(
        provider="gemini",
        model="gemini-2.5-flash-lite",
        currency="USD",
        input_per_million=0.1,
        output_per_million=0.4,
        input_cached_per_million=0.01,
        source="llm-prices:data/google.json",
    ),
    ("gemini", "gemini-2.5-flash-preview-09-2025"): ModelPrice(
        provider="gemini",
        model="gemini-2.5-flash-preview-09-2025",
        currency="USD",
        input_per_million=0.3,
        output_per_million=2.5,
        input_cached_per_million=0.03,
        source="llm-prices:data/google.json",
    ),
    ("openrouter", "google/gemini-2.5-flash"): ModelPrice(
        provider="openrouter",
        model="google/gemini-2.5-flash",
        currency="USD",
        input_per_million=0.3,
        output_per_million=2.5,
        input_cached_per_million=0.03,
        source="llm-prices:data/google.json + LLM-Price README",
        note="按 Gemini 官方价格估算",
    ),
    ("openrouter", "google/gemini-2.5-flash-lite"): ModelPrice(
        provider="openrouter",
        model="google/gemini-2.5-flash-lite",
        currency="USD",
        input_per_million=0.1,
        output_per_million=0.4,
        input_cached_per_million=0.01,
        source="llm-prices:data/google.json + LLM-Price README",
        note="按 Gemini 官方价格估算",
    ),
    ("nous", "google/gemini-2.5-flash-preview"): ModelPrice(
        provider="nous",
        model="google/gemini-2.5-flash-preview",
        currency="USD",
        input_per_million=0.3,
        output_per_million=2.5,
        input_cached_per_million=0.03,
        source="llm-prices:data/google.json",
        note="按 Gemini Flash Preview 官方价格估算",
    ),
    ("opencode-zen", "google/gemini-2.5-flash"): ModelPrice(
        provider="opencode-zen",
        model="google/gemini-2.5-flash",
        currency="USD",
        input_per_million=0.3,
        output_per_million=2.5,
        input_cached_per_million=0.03,
        source="llm-prices:data/google.json",
        note="按 Gemini 官方价格估算",
    ),
    ("kilocode", "google/gemini-2.5-flash-preview"): ModelPrice(
        provider="kilocode",
        model="google/gemini-2.5-flash-preview",
        currency="USD",
        input_per_million=0.3,
        output_per_million=2.5,
        input_cached_per_million=0.03,
        source="llm-prices:data/google.json",
        note="按 Gemini Flash Preview 官方价格估算",
    ),
    ("kimi", "kimi-k2-0905-preview"): ModelPrice(
        provider="kimi",
        model="kimi-k2-0905-preview",
        currency="USD",
        input_per_million=0.6,
        output_per_million=2.5,
        input_cached_per_million=0.15,
        source="llm-prices:data/moonshot-ai.json",
    ),
    ("kimi", "kimi-k2-turbo-preview"): ModelPrice(
        provider="kimi",
        model="kimi-k2-turbo-preview",
        currency="USD",
        input_per_million=1.15,
        output_per_million=8.0,
        input_cached_per_million=0.15,
        source="llm-prices:data/moonshot-ai.json",
    ),
    ("kimi", "kimi-k2-thinking"): ModelPrice(
        provider="kimi",
        model="kimi-k2-thinking",
        currency="USD",
        input_per_million=0.6,
        output_per_million=2.5,
        input_cached_per_million=0.15,
        source="llm-prices:data/moonshot-ai.json",
    ),
    ("qwen", "qwen3.6-plus"): ModelPrice(
        provider="qwen",
        model="qwen3.6-plus",
        currency="USD",
        input_per_million=0.5,
        output_per_million=3.0,
        source="llm-prices:data/qwen.json",
    ),
    ("qwen", "qwen3.6-plus-256k"): ModelPrice(
        provider="qwen",
        model="qwen3.6-plus-256k",
        currency="USD",
        input_per_million=2.0,
        output_per_million=6.0,
        source="llm-prices:data/qwen.json",
    ),
    ("zai", "glm-5"): ModelPrice(
        provider="zai",
        model="glm-5",
        currency="CNY",
        input_per_million=4.0,
        output_per_million=18.0,
        source="LLM-Price:README.md",
    ),
    ("minimax", "minimax-m2"): ModelPrice(
        provider="minimax",
        model="minimax-m2",
        currency="USD",
        input_per_million=0.3,
        output_per_million=1.2,
        source="llm-prices:data/minimax.json",
    ),
    ("minimax", "MiniMax-M2.7"): ModelPrice(
        provider="minimax",
        model="MiniMax-M2.7",
        currency="CNY",
        input_per_million=2.1,
        output_per_million=8.4,
        source="LLM-Price:README.md",
    ),
}


def lookup_model_price(provider: str | None, model: str | None) -> ModelPrice | None:
    normalized_provider = normalize_provider_name(provider)
    normalized_model = str(model or "").strip()
    if not normalized_model:
        return None

    direct_key = (normalized_provider, normalized_model)
    if direct_key in _PRICES:
        return _PRICES[direct_key]

    aliased_model = _MODEL_ALIASES.get(normalized_model, normalized_model)
    aliased_key = (normalized_provider, aliased_model)
    if aliased_key in _PRICES:
        return _PRICES[aliased_key]

    fallback_provider = _PROVIDER_FALLBACKS.get(normalized_provider)
    if fallback_provider:
        fallback_key = (fallback_provider, aliased_model)
        if fallback_key in _PRICES:
            price = _PRICES[fallback_key]
            return ModelPrice(
                provider=normalized_provider,
                model=normalized_model,
                currency=price.currency,
                input_per_million=price.input_per_million,
                output_per_million=price.output_per_million,
                input_cached_per_million=price.input_cached_per_million,
                source=price.source,
                note=price.note,
            )

    return None


def estimate_cost(
    price: ModelPrice,
    *,
    input_tokens: int,
    approx_output_tokens: int = 0,
) -> CostEstimate:
    input_cost = max(0, input_tokens) / 1_000_000 * price.input_per_million
    output_cost = max(0, approx_output_tokens) / 1_000_000 * price.output_per_million
    return CostEstimate(
        input_cost=input_cost,
        output_cost_if_source_tokens_match=output_cost,
        total_cost_if_source_tokens_match=input_cost + output_cost,
    )
