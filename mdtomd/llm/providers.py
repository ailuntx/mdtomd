from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ProviderDef:
    id: str
    label: str
    transport: str
    default_base_url: str = ""
    base_url_env_vars: tuple[str, ...] = ()
    api_key_env_vars: tuple[str, ...] = ()
    default_model: str = ""
    auth_scheme: str = "bearer"
    extra_headers: tuple[tuple[str, str], ...] = ()


PROVIDERS: dict[str, ProviderDef] = {
    "gemini": ProviderDef(
        id="gemini",
        label="Google Gemini",
        transport="gemini_generate_content",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        base_url_env_vars=("GEMINI_API_BASE", "GOOGLE_API_BASE"),
        api_key_env_vars=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        default_model="gemini-2.5-flash",
    ),
    "gemini-openai": ProviderDef(
        id="gemini-openai",
        label="Google Gemini (OpenAI)",
        transport="openai_chat",
        default_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        base_url_env_vars=("GEMINI_BASE_URL", "GOOGLE_API_BASE"),
        api_key_env_vars=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        default_model="gemini-2.5-flash",
    ),
    "openai": ProviderDef(
        id="openai",
        label="OpenAI",
        transport="openai_chat",
        default_base_url="https://api.openai.com/v1",
        base_url_env_vars=("OPENAI_BASE_URL",),
        api_key_env_vars=("OPENAI_API_KEY",),
        default_model="gpt-4.1-mini",
    ),
    "openai-codex": ProviderDef(
        id="openai-codex",
        label="OpenAI Codex",
        transport="openai_responses",
        default_base_url="https://chatgpt.com/backend-api/codex",
        base_url_env_vars=("OPENAI_CODEX_BASE_URL", "HERMES_CODEX_BASE_URL"),
        api_key_env_vars=("OPENAI_CODEX_ACCESS_TOKEN", "CODEX_ACCESS_TOKEN"),
        default_model="gpt-5.4-mini",
    ),
    "openrouter": ProviderDef(
        id="openrouter",
        label="OpenRouter",
        transport="openai_chat",
        default_base_url="https://openrouter.ai/api/v1",
        base_url_env_vars=("OPENROUTER_BASE_URL",),
        api_key_env_vars=("OPENROUTER_API_KEY",),
        default_model="google/gemini-2.5-flash-lite",
        extra_headers=(
            ("HTTP-Referer", "https://github.com/local/mdtomd"),
            ("X-OpenRouter-Title", "mdtomd"),
        ),
    ),
    "nous": ProviderDef(
        id="nous",
        label="Nous Portal",
        transport="openai_chat",
        default_base_url="https://inference-api.nousresearch.com/v1",
        base_url_env_vars=("NOUS_BASE_URL",),
        api_key_env_vars=("NOUS_API_KEY", "NOUS_AGENT_API_KEY"),
        default_model="google/gemini-2.5-flash-preview",
    ),
    "anthropic": ProviderDef(
        id="anthropic",
        label="Anthropic",
        transport="anthropic_messages",
        default_base_url="https://api.anthropic.com",
        base_url_env_vars=("ANTHROPIC_BASE_URL",),
        api_key_env_vars=("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN"),
        default_model="claude-3-5-sonnet-latest",
        auth_scheme="x-api-key",
    ),
    "zai": ProviderDef(
        id="zai",
        label="Z.AI / GLM",
        transport="openai_chat",
        default_base_url="https://api.z.ai/api/paas/v4",
        base_url_env_vars=("GLM_BASE_URL",),
        api_key_env_vars=("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
        default_model="glm-5",
    ),
    "deepseek": ProviderDef(
        id="deepseek",
        label="DeepSeek",
        transport="openai_chat",
        default_base_url="https://api.deepseek.com/v1",
        base_url_env_vars=("DEEPSEEK_BASE_URL",),
        api_key_env_vars=("DEEPSEEK_API_KEY",),
        default_model="deepseek-chat",
    ),
    "minimax": ProviderDef(
        id="minimax",
        label="MiniMax",
        transport="openai_chat",
        default_base_url="https://api.minimaxi.com/v1",
        base_url_env_vars=("MINIMAX_BASE_URL",),
        api_key_env_vars=("MINIMAX_API_KEY",),
        default_model="MiniMax-M1",
    ),
    "minimax-anthropic": ProviderDef(
        id="minimax-anthropic",
        label="MiniMax (Anthropic)",
        transport="anthropic_messages",
        default_base_url="https://api.minimax.io/anthropic",
        base_url_env_vars=("MINIMAX_BASE_URL",),
        api_key_env_vars=("MINIMAX_API_KEY",),
        default_model="MiniMax-M1",
    ),
    "minimax-cn": ProviderDef(
        id="minimax-cn",
        label="MiniMax China",
        transport="anthropic_messages",
        default_base_url="https://api.minimaxi.com/anthropic",
        base_url_env_vars=("MINIMAX_CN_BASE_URL",),
        api_key_env_vars=("MINIMAX_CN_API_KEY",),
        default_model="MiniMax-M1",
    ),
    "kimi": ProviderDef(
        id="kimi",
        label="Kimi",
        transport="openai_chat",
        default_base_url="https://api.moonshot.cn/v1",
        base_url_env_vars=("KIMI_BASE_URL", "MOONSHOT_BASE_URL"),
        api_key_env_vars=("KIMI_API_KEY", "MOONSHOT_API_KEY"),
        default_model="moonshot-v1-8k",
    ),
    "kimi-anthropic": ProviderDef(
        id="kimi-anthropic",
        label="Kimi Coding (Anthropic)",
        transport="anthropic_messages",
        default_base_url="https://api.kimi.com/coding",
        base_url_env_vars=("KIMI_BASE_URL", "MOONSHOT_BASE_URL"),
        api_key_env_vars=("KIMI_API_KEY", "MOONSHOT_API_KEY"),
        default_model="kimi-k2-turbo-preview",
        auth_scheme="x-api-key",
    ),
    "novita": ProviderDef(
        id="novita",
        label="Novita",
        transport="openai_chat",
        default_base_url="https://api.novita.ai/openai",
        base_url_env_vars=("NOVITA_BASE_URL",),
        api_key_env_vars=("NOVITA_API_KEY",),
        default_model="deepseek/deepseek-v3-turbo",
    ),
    "alibaba": ProviderDef(
        id="alibaba",
        label="Alibaba / DashScope",
        transport="openai_chat",
        default_base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        base_url_env_vars=("DASHSCOPE_BASE_URL",),
        api_key_env_vars=("DASHSCOPE_API_KEY",),
        default_model="qwen-plus",
    ),
    "huggingface": ProviderDef(
        id="huggingface",
        label="Hugging Face",
        transport="openai_chat",
        default_base_url="https://router.huggingface.co/v1",
        base_url_env_vars=("HF_BASE_URL",),
        api_key_env_vars=("HF_TOKEN",),
        default_model="openai/gpt-oss-120b",
    ),
    "ai-gateway": ProviderDef(
        id="ai-gateway",
        label="Vercel AI Gateway",
        transport="openai_chat",
        default_base_url="https://ai-gateway.vercel.sh/v1",
        base_url_env_vars=("AI_GATEWAY_BASE_URL",),
        api_key_env_vars=("AI_GATEWAY_API_KEY",),
        default_model="openai/gpt-4.1-mini",
    ),
    "opencode-zen": ProviderDef(
        id="opencode-zen",
        label="OpenCode Zen",
        transport="openai_chat",
        default_base_url="https://opencode.ai/zen/v1",
        base_url_env_vars=("OPENCODE_ZEN_BASE_URL",),
        api_key_env_vars=("OPENCODE_ZEN_API_KEY",),
        default_model="google/gemini-2.5-flash",
    ),
    "opencode-go": ProviderDef(
        id="opencode-go",
        label="OpenCode Go",
        transport="openai_chat",
        default_base_url="https://opencode.ai/zen/go/v1",
        base_url_env_vars=("OPENCODE_GO_BASE_URL",),
        api_key_env_vars=("OPENCODE_GO_API_KEY",),
        default_model="glm-5",
    ),
    "kilocode": ProviderDef(
        id="kilocode",
        label="Kilo Code",
        transport="openai_chat",
        default_base_url="https://api.kilo.ai/api/gateway",
        base_url_env_vars=("KILOCODE_BASE_URL",),
        api_key_env_vars=("KILOCODE_API_KEY",),
        default_model="google/gemini-2.5-flash-preview",
    ),
    "copilot": ProviderDef(
        id="copilot",
        label="GitHub Copilot",
        transport="openai_chat",
        default_base_url="https://api.githubcopilot.com",
        base_url_env_vars=("GITHUB_COPILOT_BASE_URL",),
        api_key_env_vars=("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"),
        default_model="gpt-4.1",
    ),
    "openai-compatible": ProviderDef(
        id="openai-compatible",
        label="OpenAI-Compatible",
        transport="openai_chat",
        default_base_url="",
        base_url_env_vars=("LLM_BASE_URL", "OPENAI_BASE_URL"),
        api_key_env_vars=("LLM_API_KEY", "OPENAI_API_KEY"),
        default_model="",
    ),
}


ALIASES = {
    "auto": "auto",
    "google": "gemini",
    "google-openai": "gemini-openai",
    "claude": "anthropic",
    "codex": "openai-codex",
    "openai_codex": "openai-codex",
    "chatgpt-codex": "openai-codex",
    "custom": "openai-compatible",
    "compatible": "openai-compatible",
    "openai_compatible": "openai-compatible",
    "glm": "zai",
    "z-ai": "zai",
    "z.ai": "zai",
    "zhipu": "zai",
    "moonshot": "kimi",
    "kimi-coding": "kimi",
    "kimi-for-coding": "kimi",
    "vercel": "ai-gateway",
    "kilocode": "kilocode",
    "kilo": "kilocode",
    "opencode": "opencode-zen",
    "zen": "opencode-zen",
    "dashscope": "alibaba",
    "aliyun": "alibaba",
    "qwen": "alibaba",
    "hf": "huggingface",
    "hugging-face": "huggingface",
    "github-copilot": "copilot",
    "minimax_cn": "minimax-cn",
    "minimax-china": "minimax-cn",
}


AUTO_PROVIDER_ORDER = (
    "openrouter",
    "openai",
    "anthropic",
    "gemini-openai",
    "gemini",
    "nous",
    "zai",
    "alibaba",
    "deepseek",
    "novita",
    "minimax",
    "kimi",
    "huggingface",
    "ai-gateway",
    "opencode-zen",
    "opencode-go",
    "kilocode",
    "openai-codex",
)


def normalize_provider_name(name: str | None) -> str:
    normalized = (name or "auto").strip().lower()
    return ALIASES.get(normalized, normalized)


def get_provider(name: str | None) -> ProviderDef:
    provider_name = normalize_provider_name(name)
    if provider_name == "auto":
        raise ValueError("auto is not a concrete provider")
    try:
        return PROVIDERS[provider_name]
    except KeyError as exc:
        available = ", ".join(sorted(["auto", *PROVIDERS.keys()]))
        raise ValueError(f"Unsupported provider: {name}. Available: {available}") from exc


def iter_auto_providers() -> Iterable[ProviderDef]:
    for provider_name in AUTO_PROVIDER_ORDER:
        yield PROVIDERS[provider_name]


def list_provider_defs() -> list[ProviderDef]:
    return [PROVIDERS[name] for name in sorted(PROVIDERS)]

