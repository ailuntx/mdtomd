from __future__ import annotations

from .pricing import estimate_cost, lookup_model_price


DEFAULT_FEATURED_MODELS: tuple[dict[str, str], ...] = (
    {"provider": "openai", "model": "gpt-4.1-mini", "label": "OpenAI GPT-4.1 Mini"},
    {"provider": "openai-codex", "model": "gpt-5.4-mini", "label": "OpenAI GPT-5.4 Mini"},
    {"provider": "anthropic", "model": "claude-3-5-sonnet-latest", "label": "Claude 3.5 Sonnet"},
    {"provider": "gemini", "model": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
    {"provider": "openrouter", "model": "google/gemini-2.5-flash-lite", "label": "OpenRouter Gemini 2.5 Flash Lite"},
    {"provider": "deepseek", "model": "deepseek-chat", "label": "DeepSeek Chat"},
    {"provider": "deepseek", "model": "deepseek-reasoner", "label": "DeepSeek Reasoner"},
    {"provider": "kimi", "model": "kimi-k2-turbo-preview", "label": "Kimi K2 Turbo Preview"},
    {"provider": "zai", "model": "glm-5", "label": "GLM-5"},
    {"provider": "alibaba", "model": "qwen3.6-plus", "label": "Qwen 3.6 Plus"},
)


def get_featured_models(config) -> list[dict[str, str]]:
    configured = []
    for item in config.display.featured_models.values():
        provider = str(item.provider or "").strip()
        model = str(item.model or "").strip()
        if not provider or not model:
            continue
        configured.append(
            {
                "provider": provider,
                "model": model,
                "label": str(item.label or "").strip(),
            }
        )
    return (configured or list(DEFAULT_FEATURED_MODELS))[:10]


def format_price_brief(price) -> str:
    if price is None:
        return "-"
    return f"{price.currency} in={price.input_per_million}/MTokens out={price.output_per_million}/MTokens"


def build_price_summary(
    *,
    provider: str | None,
    model: str | None,
    input_tokens: int,
    approx_output_tokens: int,
) -> list[str]:
    price = lookup_model_price(provider, model)
    if price is None:
        return ["价格: 未内置该 provider/model 的单价"]

    cost = estimate_cost(price, input_tokens=input_tokens, approx_output_tokens=approx_output_tokens)
    lines = [
        f"价格: {price.currency} input={price.input_per_million}/MTokens output={price.output_per_million}/MTokens",
        f"预计输入成本: {cost.input_cost:.6f} {price.currency}",
        f"粗估总成本: {cost.total_cost_if_source_tokens_match:.6f} {price.currency} (按输出 tokens≈原文 tokens)",
    ]
    if price.note:
        lines.append(f"价格说明: {price.note}")
    if price.source:
        lines.append(f"价格来源: {price.source}")
    return lines


def build_featured_price_summary(
    *,
    config,
    input_tokens: int,
    approx_output_tokens: int,
) -> list[str]:
    lines = ["推荐模型费用:"]
    for item in get_featured_models(config):
        provider = item["provider"]
        model = item["model"]
        label = item["label"] or model
        price = lookup_model_price(provider, model)
        if price is None:
            lines.append(f"- {label} | {provider} / {model} | 未内置价格")
            continue
        cost = estimate_cost(price, input_tokens=input_tokens, approx_output_tokens=approx_output_tokens)
        lines.append(
            f"- {label} | {provider} / {model} | input={cost.input_cost:.6f} {price.currency} | total={cost.total_cost_if_source_tokens_match:.6f} {price.currency}"
        )
    return lines

