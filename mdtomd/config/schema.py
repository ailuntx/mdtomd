from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "auto"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    api_key_env: str = ""
    codex_home: str = ""
    auth_file: str = ""
    api_mode: str = "auto"
    timeout_sec: float = 120.0
    max_tokens: int = 8192
    temperature: float = 0.0
    max_retries: int = 2
    retry_base_delay: float = 1.5


@dataclass(frozen=True)
class ProviderOverrideConfig:
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    api_key_env: str = ""
    codex_home: str = ""
    auth_file: str = ""
    api_mode: str = ""
    timeout_sec: float | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    max_retries: int | None = None
    retry_base_delay: float | None = None

    def as_mapping(self) -> dict[str, object]:
        return {
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "api_key_env": self.api_key_env,
            "codex_home": self.codex_home,
            "auth_file": self.auth_file,
            "api_mode": self.api_mode,
            "timeout_sec": self.timeout_sec,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "max_retries": self.max_retries,
            "retry_base_delay": self.retry_base_delay,
        }


@dataclass(frozen=True)
class TranslatorConfig:
    chunk_size: int | None = None
    chunk_sleep_seconds: float = 0.5


@dataclass(frozen=True)
class DefaultsConfig:
    language: str = ""
    output_dir: str = ""
    suffix: str = ""
    flat: bool = False
    force: bool = False


@dataclass(frozen=True)
class FeaturedModelConfig:
    provider: str = ""
    model: str = ""
    label: str = ""


@dataclass(frozen=True)
class DisplayConfig:
    featured_models: dict[str, FeaturedModelConfig] = field(default_factory=dict)


@dataclass(frozen=True)
class AppConfig:
    path: str = ""
    llm: LLMConfig = field(default_factory=LLMConfig)
    providers: dict[str, ProviderOverrideConfig] = field(default_factory=dict)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    translator: TranslatorConfig = field(default_factory=TranslatorConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
