from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import (
    AppConfig,
    DefaultsConfig,
    DisplayConfig,
    FeaturedModelConfig,
    LLMConfig,
    ProviderOverrideConfig,
    TranslatorConfig,
)
from .simple_yaml import load_simple_yaml


DEFAULT_CONFIG_FILES = ("config.yaml", "config.yml")


def resolve_config_path(explicit: str | None = None, cwd: str | None = None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()

    base = Path(cwd or ".")
    for name in DEFAULT_CONFIG_FILES:
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


def load_config(explicit: str | None = None, cwd: str | None = None) -> AppConfig:
    path = resolve_config_path(explicit, cwd=cwd)
    if path is None:
        return AppConfig()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = load_simple_yaml(path.read_text(encoding="utf-8"))
    return AppConfig(
        path=str(path),
        llm=_parse_llm_config(raw.get("llm") or {}),
        providers=_parse_provider_overrides(raw.get("providers") or {}),
        display=_parse_display_config(raw.get("display") or {}),
        translator=_parse_translator_config(raw.get("translator") or {}),
        defaults=_parse_defaults_config(raw.get("defaults") or {}),
    )


def _parse_llm_config(raw: dict[str, Any]) -> LLMConfig:
    if not isinstance(raw, dict):
        return LLMConfig()
    return LLMConfig(
        provider=_read_string(raw, "provider", "auto"),
        model=_read_string(raw, "model", ""),
        base_url=_read_string(raw, "base_url", ""),
        api_key=_read_string(raw, "api_key", ""),
        api_key_env=_read_string(raw, "api_key_env", ""),
        codex_home=_read_string(raw, "codex_home", ""),
        auth_file=_read_string(raw, "auth_file", ""),
        api_mode=_read_string(raw, "api_mode", "auto"),
        timeout_sec=_read_float(raw, "timeout_sec", 120.0),
        max_tokens=_read_int(raw, "max_tokens", 8192),
        temperature=_read_float(raw, "temperature", 0.0),
        max_retries=_read_int(raw, "max_retries", 2),
        retry_base_delay=_read_float(raw, "retry_base_delay", 1.5),
    )


def _parse_provider_overrides(raw: dict[str, Any]) -> dict[str, ProviderOverrideConfig]:
    if not isinstance(raw, dict):
        return {}

    parsed: dict[str, ProviderOverrideConfig] = {}
    for provider_name, provider_raw in raw.items():
        if not isinstance(provider_raw, dict):
            continue
        parsed[str(provider_name)] = ProviderOverrideConfig(
            model=_read_string(provider_raw, "model", ""),
            base_url=_read_string(provider_raw, "base_url", ""),
            api_key=_read_string(provider_raw, "api_key", ""),
            api_key_env=_read_string(provider_raw, "api_key_env", ""),
            codex_home=_read_string(provider_raw, "codex_home", ""),
            auth_file=_read_string(provider_raw, "auth_file", ""),
            api_mode=_read_string(provider_raw, "api_mode", ""),
            timeout_sec=_read_optional_float(provider_raw, "timeout_sec"),
            max_tokens=_read_optional_int(provider_raw, "max_tokens"),
            temperature=_read_optional_float(provider_raw, "temperature"),
            max_retries=_read_optional_int(provider_raw, "max_retries"),
            retry_base_delay=_read_optional_float(provider_raw, "retry_base_delay"),
        )
    return parsed


def _parse_translator_config(raw: dict[str, Any]) -> TranslatorConfig:
    if not isinstance(raw, dict):
        return TranslatorConfig()
    return TranslatorConfig(
        chunk_size=_read_optional_int(raw, "chunk_size"),
        chunk_sleep_seconds=_read_float(raw, "chunk_sleep_seconds", 0.5),
    )


def _parse_defaults_config(raw: dict[str, Any]) -> DefaultsConfig:
    if not isinstance(raw, dict):
        return DefaultsConfig()
    return DefaultsConfig(
        language=_read_string(raw, "language", ""),
        output_dir=_read_string(raw, "output_dir", ""),
        suffix=_read_string(raw, "suffix", ""),
        flat=bool(raw.get("flat", False)),
        force=bool(raw.get("force", False)),
    )


def _parse_display_config(raw: dict[str, Any]) -> DisplayConfig:
    if not isinstance(raw, dict):
        return DisplayConfig()

    featured_models_raw = raw.get("featured_models") or {}
    if not isinstance(featured_models_raw, dict):
        return DisplayConfig()

    featured_models: dict[str, FeaturedModelConfig] = {}
    for item_name, item_raw in featured_models_raw.items():
        if not isinstance(item_raw, dict):
            continue
        featured_models[str(item_name)] = FeaturedModelConfig(
            provider=_read_string(item_raw, "provider", ""),
            model=_read_string(item_raw, "model", ""),
            label=_read_string(item_raw, "label", ""),
        )
    return DisplayConfig(featured_models=featured_models)


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == {} or value == []


def _read_string(raw: dict[str, Any], key: str, default: str) -> str:
    value = raw.get(key)
    if _is_missing(value):
        return default
    return str(value)


def _read_int(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key)
    if _is_missing(value):
        return default
    return int(value)


def _read_optional_int(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if _is_missing(value):
        return None
    return int(value)


def _read_float(raw: dict[str, Any], key: str, default: float) -> float:
    value = raw.get(key)
    if _is_missing(value):
        return default
    return float(value)


def _read_optional_float(raw: dict[str, Any], key: str) -> float | None:
    value = raw.get(key)
    if _is_missing(value):
        return None
    return float(value)
