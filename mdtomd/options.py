from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from .config import AppConfig
from .llm.providers import get_provider, normalize_provider_name


@dataclass(frozen=True)
class TranslateCommandOptions:
    input: str
    language: str
    output: str | None
    output_dir: str
    provider: str
    model: str
    base_url: str
    api_key: str
    api_key_env: str
    codex_home: str
    auth_file: str
    api_mode: str
    chunk_size: int
    chunk_sleep_seconds: float
    timeout_sec: float
    max_tokens: int
    temperature: float
    max_retries: int
    retry_base_delay: float
    flat: bool
    suffix: str
    translated_suffix_aliases: tuple[str, ...]
    force: bool

    def llm_kwargs(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model or None,
            "base_url": self.base_url or None,
            "api_key": self.api_key or None,
            "api_key_env": self.api_key_env or None,
            "codex_home": self.codex_home or None,
            "auth_file": self.auth_file or None,
            "api_mode": self.api_mode,
            "timeout_sec": self.timeout_sec,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "max_retries": self.max_retries,
            "retry_base_delay": self.retry_base_delay,
        }


@dataclass(frozen=True)
class EstimateCommandOptions:
    input: str
    language: str
    output: str | None
    output_dir: str
    provider: str
    model: str
    resolved_model: str
    chunk_size: int
    max_tokens: int
    flat: bool
    suffix: str
    translated_suffix_aliases: tuple[str, ...]
    force: bool


def resolve_translate_options(args: Any, config: AppConfig) -> TranslateCommandOptions:
    provider = _arg_str(args, "provider") or _env_str("MD_TRANSLATE_PROVIDER") or config.llm.provider
    provider_override = _get_provider_override(config, provider)
    arg_flat = getattr(args, "flat", None)
    arg_force = getattr(args, "force", None)
    max_tokens = _resolve_max_tokens(args, provider_override, config)
    chunk_size = _resolve_chunk_size(args, config, max_tokens)

    return TranslateCommandOptions(
        input=str(getattr(args, "input")),
        language=_arg_str(args, "language") or _env_str("MD_TRANSLATE_LANGUAGE") or config.defaults.language,
        output=getattr(args, "output", None),
        output_dir=_arg_str(args, "output_dir") or _env_str("MD_TRANSLATE_OUTPUT_DIR") or config.defaults.output_dir,
        provider=provider,
        model=_arg_str(args, "model") or _env_str("MD_TRANSLATE_MODEL") or str(provider_override.get("model", "") or "") or config.llm.model,
        base_url=_arg_str(args, "base_url") or _env_str("MD_TRANSLATE_BASE_URL") or str(provider_override.get("base_url", "") or "") or config.llm.base_url,
        api_key=_arg_str(args, "api_key") or _env_str("MD_TRANSLATE_API_KEY") or str(provider_override.get("api_key", "") or "") or config.llm.api_key,
        api_key_env=_arg_str(args, "api_key_env") or _env_str("MD_TRANSLATE_API_KEY_ENV") or str(provider_override.get("api_key_env", "") or "") or config.llm.api_key_env,
        codex_home=_arg_str(args, "codex_home") or _env_str("MD_TRANSLATE_CODEX_HOME") or str(provider_override.get("codex_home", "") or "") or config.llm.codex_home,
        auth_file=_arg_str(args, "auth_file") or _env_str("MD_TRANSLATE_CODEX_AUTH_FILE") or str(provider_override.get("auth_file", "") or "") or config.llm.auth_file,
        api_mode=_arg_str(args, "api_mode") or _env_str("MD_TRANSLATE_API_MODE") or str(provider_override.get("api_mode", "") or "") or config.llm.api_mode,
        chunk_size=chunk_size,
        chunk_sleep_seconds=_coalesce(
            _arg_value(args, "chunk_sleep_seconds"),
            _env_float("MD_TRANSLATE_CHUNK_SLEEP_SECONDS"),
            config.translator.chunk_sleep_seconds,
        ),
        timeout_sec=_coalesce(
            _arg_value(args, "timeout_sec"),
            _env_float("MD_TRANSLATE_TIMEOUT_SEC"),
            provider_override.get("timeout_sec"),
            config.llm.timeout_sec,
        ),
        max_tokens=max_tokens,
        temperature=_coalesce(
            _arg_value(args, "temperature"),
            _env_float("MD_TRANSLATE_TEMPERATURE"),
            provider_override.get("temperature"),
            config.llm.temperature,
        ),
        max_retries=_coalesce(
            _arg_value(args, "max_retries"),
            _env_int("MD_TRANSLATE_MAX_RETRIES"),
            provider_override.get("max_retries"),
            config.llm.max_retries,
        ),
        retry_base_delay=_coalesce(
            _arg_value(args, "retry_base_delay"),
            _env_float("MD_TRANSLATE_RETRY_BASE_DELAY"),
            provider_override.get("retry_base_delay"),
            config.llm.retry_base_delay,
        ),
        flat=arg_flat if arg_flat is not None else config.defaults.flat,
        suffix=_arg_str(args, "suffix") or _env_str("MD_TRANSLATE_SUFFIX") or config.defaults.suffix,
        translated_suffix_aliases=_parse_suffix_aliases(_arg_value(args, "translated_suffix_aliases")) or _parse_suffix_aliases(_env_str("MD_TRANSLATE_SUFFIX_ALIASES")),
        force=arg_force if arg_force is not None else config.defaults.force,
    )


def resolve_estimate_options(args: Any, config: AppConfig) -> EstimateCommandOptions:
    provider = _arg_str(args, "provider") or _env_str("MD_TRANSLATE_PROVIDER") or config.llm.provider
    provider_override = _get_provider_override(config, provider)
    model = _arg_str(args, "model") or _env_str("MD_TRANSLATE_MODEL") or str(provider_override.get("model", "") or "") or config.llm.model
    arg_flat = getattr(args, "flat", None)
    arg_force = getattr(args, "force", None)
    max_tokens = _resolve_max_tokens(args, provider_override, config)
    chunk_size = _resolve_chunk_size(args, config, max_tokens)

    return EstimateCommandOptions(
        input=str(getattr(args, "input")),
        language=_arg_str(args, "language") or _env_str("MD_TRANSLATE_LANGUAGE") or config.defaults.language,
        output=getattr(args, "output", None),
        output_dir=_arg_str(args, "output_dir") or _env_str("MD_TRANSLATE_OUTPUT_DIR") or config.defaults.output_dir,
        provider=provider,
        model=model,
        resolved_model=resolve_estimate_model(provider, model),
        chunk_size=chunk_size,
        max_tokens=max_tokens,
        flat=arg_flat if arg_flat is not None else config.defaults.flat,
        suffix=_arg_str(args, "suffix") or _env_str("MD_TRANSLATE_SUFFIX") or config.defaults.suffix,
        translated_suffix_aliases=_parse_suffix_aliases(_arg_value(args, "translated_suffix_aliases")) or _parse_suffix_aliases(_env_str("MD_TRANSLATE_SUFFIX_ALIASES")),
        force=arg_force if arg_force is not None else config.defaults.force,
    )


def resolve_estimate_model(provider: str | None, model: str | None) -> str:
    resolved_model = str(model or "").strip()
    if resolved_model:
        return resolved_model
    provider_name = normalize_provider_name(provider)
    if provider_name == "auto":
        return ""
    try:
        return get_provider(provider_name).default_model
    except ValueError:
        return ""


def _get_provider_override(config: AppConfig, provider: str | None) -> dict[str, object]:
    provider_name = normalize_provider_name(provider)
    if provider_name == "auto":
        return {}

    provider_config = config.providers.get(provider_name)
    if provider_config is None:
        for candidate_name, candidate_config in config.providers.items():
            if normalize_provider_name(candidate_name) == provider_name:
                provider_config = candidate_config
                break

    return provider_config.as_mapping() if provider_config is not None else {}


def _resolve_max_tokens(args: Any, provider_override: dict[str, object], config: AppConfig) -> int:
    return int(
        _coalesce(
            _arg_value(args, "max_tokens"),
            _env_int("MD_TRANSLATE_MAX_TOKENS"),
            provider_override.get("max_tokens"),
            config.llm.max_tokens,
        )
    )


def _resolve_chunk_size(args: Any, config: AppConfig, max_tokens: int) -> int:
    return int(
        _coalesce(
            _arg_value(args, "chunk_size"),
            _env_int("MD_TRANSLATE_CHUNK_SIZE"),
            config.translator.chunk_size,
            max_tokens,
        )
    )


def _arg_value(args: Any, name: str) -> Any:
    return getattr(args, name, None)


def _arg_str(args: Any, name: str) -> str:
    value = _arg_value(args, name)
    return str(value or "").strip()


def _env_str(name: str) -> str:
    return os.getenv(name, "").strip()


def _env_int(name: str) -> int | None:
    value = _env_str(name)
    if not value:
        return None
    return int(value)


def _env_float(name: str) -> float | None:
    value = _env_str(name)
    if not value:
        return None
    return float(value)


def _coalesce(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _parse_suffix_aliases(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        raw_items = [str(item or "") for item in value]
    else:
        raw_items = re.split(r"[\s,;]+", str(value or ""))

    aliases: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        normalized = str(item or "").strip().strip("_").lower()
        if normalized and normalized not in seen:
            aliases.append(normalized)
            seen.add(normalized)
    return tuple(aliases)
