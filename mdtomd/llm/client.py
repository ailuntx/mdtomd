from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from .providers import ProviderDef, get_provider, iter_auto_providers, list_provider_defs


_RESPONSES_PREFERRED_PREFIXES = ("gpt-5", "o3", "o4")
_NO_TEMPERATURE_MODEL_PREFIXES = ("o3", "o4")


@dataclass(frozen=True)
class LLMRuntimeConfig:
    provider: str
    transport: str
    model: str
    base_url: str
    api_key: str
    timeout_sec: float = 120.0
    max_tokens: int = 8192
    temperature: float = 0.1
    max_retries: int = 2
    retry_base_delay: float = 1.5


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    raw: dict[str, Any] = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = ""


def _read_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _decode_jwt_claims(token: str) -> dict[str, Any]:
    if not isinstance(token, str) or token.count(".") != 2:
        return {}
    payload = token.split(".")[1]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload.encode("utf-8"))
        claims = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return claims if isinstance(claims, dict) else {}


def _codex_access_token_is_expiring(token: str, skew_seconds: int = 0) -> bool:
    claims = _decode_jwt_claims(token)
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        return False
    return float(exp) <= (time.time() + max(0, int(skew_seconds)))


def _read_codex_cli_access_token(*, codex_home: str | None = None, auth_file: str | None = None) -> str:
    explicit_auth_file = (auth_file or "").strip()
    explicit_codex_home = (codex_home or "").strip()
    env_codex_home = os.getenv("CODEX_HOME", "").strip()
    if explicit_auth_file:
        auth_path = Path(explicit_auth_file).expanduser()
    elif explicit_codex_home:
        auth_path = Path(explicit_codex_home).expanduser() / "auth.json"
    elif env_codex_home:
        auth_path = Path(env_codex_home).expanduser() / "auth.json"
    else:
        auth_path = Path.home() / ".codex" / "auth.json"

    if not auth_path.is_file():
        return ""

    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        return ""
    access_token = str(tokens.get("access_token", "") or "").strip()
    if not access_token:
        return ""
    if _codex_access_token_is_expiring(access_token, 0):
        return ""
    return access_token


def _create_openai_sdk_client(*, api_key: str, base_url: str, timeout_sec: float):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Provider openai-codex requires the `openai` package. "
            "Install it with `python3 -m pip install openai`."
        ) from exc
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_sec)


def _should_use_responses_api(provider: ProviderDef, base_url: str, model: str, api_mode: str) -> bool:
    normalized_mode = (api_mode or "auto").strip().lower()
    if normalized_mode == "responses":
        return True
    if normalized_mode == "chat_completions":
        return False
    if provider.transport != "openai_chat":
        return False
    normalized_url = (base_url or "").strip().lower().rstrip("/")
    return provider.id == "openai" and normalized_url.endswith("/v1") and model.startswith(_RESPONSES_PREFERRED_PREFIXES)


def _build_auth_headers(provider: ProviderDef, api_key: str) -> dict[str, str]:
    if provider.auth_scheme == "x-api-key":
        return {"x-api-key": api_key}
    return {"Authorization": f"Bearer {api_key}"}


def _resolve_provider_runtime(
    provider: ProviderDef,
    *,
    model: str | None,
    base_url: str | None,
    api_key: str | None,
    api_key_env: str | None,
    codex_home: str | None,
    auth_file: str | None,
    api_mode: str,
    timeout_sec: float,
    max_tokens: int,
    temperature: float,
    max_retries: int,
    retry_base_delay: float,
) -> LLMRuntimeConfig:
    resolved_key = (api_key or "").strip()
    if not resolved_key and api_key_env:
        resolved_key = os.getenv(api_key_env, "").strip()
    if not resolved_key:
        resolved_key = _read_env(provider.api_key_env_vars)
    if not resolved_key and provider.id == "openai-codex":
        resolved_key = _read_codex_cli_access_token(codex_home=codex_home, auth_file=auth_file)
    if not resolved_key:
        if provider.id == "openai-codex":
            raise ValueError(
                "Provider openai-codex is missing access token. "
                "Run `codex login`, or set OPENAI_CODEX_ACCESS_TOKEN / CODEX_ACCESS_TOKEN, "
                "or configure codex_home / auth_file."
            )
        env_names = ", ".join(provider.api_key_env_vars) or (api_key_env or "custom env")
        raise ValueError(f"Provider {provider.id} is missing API key. Expected: {env_names}")

    resolved_base_url = (base_url or "").strip()
    if not resolved_base_url:
        resolved_base_url = _read_env(provider.base_url_env_vars) or provider.default_base_url
    if provider.id == "openai-compatible" and not resolved_base_url:
        raise ValueError("Provider openai-compatible requires --base-url or LLM_BASE_URL")

    resolved_model = (model or "").strip() or provider.default_model
    if not resolved_model:
        raise ValueError(f"Provider {provider.id} requires --model")

    transport = provider.transport
    if _should_use_responses_api(provider, resolved_base_url, resolved_model, api_mode):
        transport = "openai_responses"

    return LLMRuntimeConfig(
        provider=provider.id,
        transport=transport,
        model=resolved_model,
        base_url=resolved_base_url.rstrip("/"),
        api_key=resolved_key,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        temperature=temperature,
        max_retries=max_retries,
        retry_base_delay=retry_base_delay,
    )


def resolve_runtime_config(
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    api_key_env: str | None = None,
    codex_home: str | None = None,
    auth_file: str | None = None,
    api_mode: str = "auto",
    timeout_sec: float = 120.0,
    max_tokens: int = 8192,
    temperature: float = 0.1,
    max_retries: int = 2,
    retry_base_delay: float = 1.5,
) -> LLMRuntimeConfig:
    requested = (provider or "auto").strip()
    if requested and requested.lower() != "auto":
        return _resolve_provider_runtime(
            get_provider(requested),
            model=model,
            base_url=base_url,
            api_key=api_key,
            api_key_env=api_key_env,
            codex_home=codex_home,
            auth_file=auth_file,
            api_mode=api_mode,
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
        )

    if (api_key or "").strip() and not (base_url or "").strip():
        raise ValueError("When using --api-key directly with provider=auto, please also set --provider")

    if (base_url or "").strip() and ((api_key or "").strip() or (api_key_env and os.getenv(api_key_env, "").strip())):
        return _resolve_provider_runtime(
            get_provider("openai-compatible"),
            model=model,
            base_url=base_url,
            api_key=api_key,
            api_key_env=api_key_env,
            codex_home=codex_home,
            auth_file=auth_file,
            api_mode=api_mode,
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
        )

    errors: list[str] = []
    for candidate in iter_auto_providers():
        try:
            return _resolve_provider_runtime(
                candidate,
                model=model,
                base_url=base_url,
                api_key=api_key,
                api_key_env=api_key_env,
                codex_home=codex_home,
                auth_file=auth_file,
                api_mode=api_mode,
                timeout_sec=timeout_sec,
                max_tokens=max_tokens,
                temperature=temperature,
                max_retries=max_retries,
                retry_base_delay=retry_base_delay,
            )
        except ValueError as exc:
            errors.append(str(exc))
    raise ValueError("No available provider found. Set --provider/--api-key or configure one of the supported API key env vars.")


class LLMClient:
    def __init__(self, config: LLMRuntimeConfig) -> None:
        self.config = config
        self.provider = get_provider(config.provider)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        prompt_messages = [dict(item) for item in messages]
        if system:
            prompt_messages.insert(0, {"role": "system", "content": system})

        current_max_tokens = max_tokens or self.config.max_tokens
        current_temperature = self.config.temperature if temperature is None else temperature
        if self.config.transport == "anthropic_messages" and self.config.model.startswith(("claude-3-7", "claude-4")):
            current_temperature = 1.0

        for attempt in range(self.config.max_retries + 1):
            try:
                return self._raw_chat(prompt_messages, current_max_tokens, current_temperature)
            except Exception:
                if attempt >= self.config.max_retries:
                    raise
                time.sleep(self.config.retry_base_delay * (2**attempt))
        raise RuntimeError("LLM request failed")

    def _raw_chat(self, messages: list[dict[str, str]], max_tokens: int, temperature: float) -> LLMResponse:
        if self.config.transport == "openai_chat":
            payload = self._build_openai_chat_payload(messages, max_tokens, temperature)
            data = self._post_json(
                f"{self.config.base_url}/chat/completions",
                payload,
                {
                    "Content-Type": "application/json; charset=utf-8",
                    **_build_auth_headers(self.provider, self.config.api_key),
                },
            )
            return self._parse_openai_chat_response(data)

        if self.config.transport == "openai_responses":
            if self.provider.id == "openai-codex":
                return self._sdk_codex_chat(messages)
            payload = self._build_openai_responses_payload(messages, max_tokens, temperature)
            data = self._post_json(
                f"{self.config.base_url}/responses",
                payload,
                {
                    "Content-Type": "application/json; charset=utf-8",
                    **_build_auth_headers(self.provider, self.config.api_key),
                },
            )
            return self._parse_openai_responses_response(data)

        if self.config.transport == "anthropic_messages":
            payload = self._build_anthropic_payload(messages, max_tokens, temperature)
            data = self._post_json(
                f"{self.config.base_url}/v1/messages",
                payload,
                {
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json; charset=utf-8",
                    **_build_auth_headers(self.provider, self.config.api_key),
                },
            )
            return self._parse_anthropic_response(data)

        if self.config.transport == "gemini_generate_content":
            encoded_model = parse.quote(self.config.model, safe="")
            encoded_key = parse.quote(self.config.api_key, safe="")
            payload = self._build_gemini_payload(messages)
            data = self._post_json(
                f"{self.config.base_url}/models/{encoded_model}:generateContent?key={encoded_key}",
                payload,
                {"Content-Type": "application/json; charset=utf-8"},
            )
            return self._parse_gemini_response(data)

        raise RuntimeError(f"Unsupported transport: {self.config.transport}")

    def _sdk_codex_chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        client = _create_openai_sdk_client(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout_sec=self.config.timeout_sec,
        )

        instructions_parts: list[str] = []
        input_messages: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "user") or "user")
            content = str(message.get("content", "") or "")
            if role == "system":
                if content:
                    instructions_parts.append(content)
                continue
            input_messages.append({"role": role, "content": content})

        request_kwargs: dict[str, Any] = {
            "model": self.config.model,
            "instructions": "\n\n".join(instructions_parts) if instructions_parts else "You are a helpful assistant.",
            "input": input_messages or [{"role": "user", "content": "Continue."}],
            "store": False,
        }

        try:
            with client.responses.stream(**request_kwargs) as stream:
                streamed_text_parts: list[str] = []
                collected_output_items: list[Any] = []
                for event in stream:
                    event_type = getattr(event, "type", "")
                    if event_type in {"response.output_text.delta", "output_text.delta"}:
                        delta_text = getattr(event, "delta", "")
                        if delta_text:
                            streamed_text_parts.append(str(delta_text))
                    elif event_type == "response.output_item.done":
                        done_item = getattr(event, "item", None)
                        if done_item is not None:
                            collected_output_items.append(done_item)
                response = stream.get_final_response()
        except Exception as exc:
            raise RuntimeError(f"{self.config.provider} request failed: {exc}") from exc

        data = response.model_dump(mode="json") if hasattr(response, "model_dump") else {}
        if not data.get("output_text"):
            if collected_output_items:
                normalized_output = []
                for item in collected_output_items:
                    if hasattr(item, "model_dump"):
                        normalized_output.append(item.model_dump(mode="json"))
                if normalized_output:
                    data["output"] = normalized_output
            if not data.get("output_text") and streamed_text_parts:
                data["output_text"] = "".join(streamed_text_parts)
        return self._parse_openai_responses_response(data)

    def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        merged_headers = dict(headers)
        for key, value in self.provider.extra_headers:
            merged_headers.setdefault(key, value)
        req = request.Request(url, data=body, headers=merged_headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.config.timeout_sec) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{self.config.provider} request failed: {self._extract_error_message(detail)}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"{self.config.provider} request failed: {exc.reason}") from exc

    def _build_openai_chat_payload(self, messages: list[dict[str, str]], max_tokens: int, temperature: float) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.config.model, "messages": messages}
        if not self.config.model.startswith(_NO_TEMPERATURE_MODEL_PREFIXES):
            payload["temperature"] = temperature
        if self.config.model.startswith(_RESPONSES_PREFERRED_PREFIXES):
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens
        return payload

    def _build_openai_responses_payload(self, messages: list[dict[str, str]], max_tokens: int, temperature: float) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "input": [
                {
                    "role": str(message.get("role", "user") or "user"),
                    "content": [{"type": "input_text", "text": str(message.get("content", "") or "")}],
                }
                for message in messages
            ],
            "max_output_tokens": max_tokens,
        }
        if not self.config.model.startswith(_NO_TEMPERATURE_MODEL_PREFIXES):
            payload["temperature"] = temperature
        return payload

    def _build_anthropic_payload(self, messages: list[dict[str, str]], max_tokens: int, temperature: float) -> dict[str, Any]:
        system_parts: list[str] = []
        chat_messages: list[dict[str, str]] = []
        for message in messages:
            role = str(message.get("role", "user") or "user")
            content = str(message.get("content", "") or "")
            if role == "system":
                system_parts.append(content)
                continue
            if chat_messages and chat_messages[-1]["role"] == role:
                chat_messages[-1]["content"] = f"{chat_messages[-1]['content']}\n\n{content}"
            else:
                chat_messages.append({"role": role, "content": content})

        if not chat_messages:
            chat_messages = [{"role": "user", "content": "Translate the provided markdown."}]
        elif chat_messages[0]["role"] != "user":
            chat_messages.insert(0, {"role": "user", "content": "Continue."})

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        return payload

    @staticmethod
    def _build_gemini_payload(messages: list[dict[str, str]]) -> dict[str, Any]:
        parts = []
        for message in messages:
            role = str(message.get("role", "user") or "user")
            content = str(message.get("content", "") or "")
            prefix = "System" if role == "system" else role.capitalize()
            parts.append({"text": f"{prefix}:\n{content}"})
        return {"contents": [{"parts": parts}]}

    @staticmethod
    def _extract_error_message(payload: str) -> str:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return payload.strip() or "Unknown API error"
        if isinstance(data, dict):
            error_info = data.get("error")
            if isinstance(error_info, dict):
                message = error_info.get("message")
                if message:
                    return str(message)
        return payload.strip() or "Unknown API error"

    @staticmethod
    def _coerce_openai_message_content(content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"} and item.get("text"):
                    texts.append(str(item["text"]))
            return "".join(texts).strip()
        return ""

    def _parse_openai_chat_response(self, data: dict[str, Any]) -> LLMResponse:
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"{self.config.provider} returned no choices")
        choice = choices[0]
        usage = data.get("usage") or {}
        message = choice.get("message") or {}
        content = self._coerce_openai_message_content(message.get("content"))
        return LLMResponse(
            content=content,
            model=str(data.get("model") or self.config.model),
            raw=data,
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
            finish_reason=str(choice.get("finish_reason") or ""),
        )

    def _parse_openai_responses_response(self, data: dict[str, Any]) -> LLMResponse:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            content = output_text.strip()
        else:
            chunks: list[str] = []
            for item in data.get("output") or []:
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                for content_item in item.get("content") or []:
                    if isinstance(content_item, dict) and content_item.get("type") in {"output_text", "text"} and content_item.get("text"):
                        chunks.append(str(content_item["text"]))
            content = "".join(chunks).strip()

        usage = data.get("usage") or {}
        return LLMResponse(
            content=content,
            model=str(data.get("model") or self.config.model),
            raw=data,
            prompt_tokens=int(usage.get("input_tokens", 0) or 0),
            completion_tokens=int(usage.get("output_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
            finish_reason=str(data.get("status") or ""),
        )

    def _parse_anthropic_response(self, data: dict[str, Any]) -> LLMResponse:
        content_parts = []
        for item in data.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                content_parts.append(str(item["text"]))
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("input_tokens", 0) or 0)
        completion_tokens = int(usage.get("output_tokens", 0) or 0)
        return LLMResponse(
            content="".join(content_parts).strip(),
            model=str(data.get("model") or self.config.model),
            raw=data,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason=str(data.get("stop_reason") or ""),
        )

    def _parse_gemini_response(self, data: dict[str, Any]) -> LLMResponse:
        candidates = data.get("candidates") or []
        for candidate in candidates:
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            texts = [str(part.get("text")) for part in parts if isinstance(part, dict) and part.get("text")]
            if texts:
                return LLMResponse(
                    content="".join(texts).strip(),
                    model=self.config.model,
                    raw=data,
                    finish_reason=str(candidate.get("finishReason") or ""),
                )

        prompt_feedback = data.get("promptFeedback") or {}
        block_reason = prompt_feedback.get("blockReason")
        if block_reason:
            raise RuntimeError(f"gemini request blocked: {block_reason}")
        raise RuntimeError("gemini returned no text content")


def create_llm_client(
    *,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    api_key_env: str | None = None,
    codex_home: str | None = None,
    auth_file: str | None = None,
    api_mode: str = "auto",
    timeout_sec: float = 120.0,
    max_tokens: int = 8192,
    temperature: float = 0.1,
    max_retries: int = 2,
    retry_base_delay: float = 1.5,
) -> LLMClient:
    return LLMClient(
        resolve_runtime_config(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            api_key_env=api_key_env,
            codex_home=codex_home,
            auth_file=auth_file,
            api_mode=api_mode,
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
            temperature=temperature,
            max_retries=max_retries,
            retry_base_delay=retry_base_delay,
        )
    )


def list_supported_providers() -> list[dict[str, str]]:
    rows = []
    for provider in list_provider_defs():
        rows.append(
            {
                "id": provider.id,
                "label": provider.label,
                "transport": provider.transport,
                "default_model": provider.default_model,
                "api_key_envs": ", ".join(provider.api_key_env_vars),
            }
        )
    return rows

