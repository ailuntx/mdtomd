from types import SimpleNamespace
from unittest import TestCase

from mdtomd.config import load_config
from mdtomd.options import resolve_estimate_options, resolve_translate_options


class OptionsTests(TestCase):
    def test_resolve_translate_options_prefers_cli_codex_fields(self) -> None:
        options = resolve_translate_options(
            SimpleNamespace(
                input="README.md",
                language="Chinese",
                output=None,
                output_dir="",
                provider="openai-codex",
                model="gpt-5.4-mini",
                base_url="https://chatgpt.com/backend-api/codex",
                api_key="",
                api_key_env="OPENAI_CODEX_ACCESS_TOKEN",
                codex_home="/tmp/codex-home",
                auth_file="/tmp/codex-home/auth.json",
                api_mode="responses",
                chunk_size=None,
                chunk_sleep_seconds=None,
                timeout_sec=None,
                max_tokens=64000,
                temperature=None,
                max_retries=None,
                retry_base_delay=None,
                flat=None,
                suffix="zh",
                force=None,
            ),
            load_config(),
        )

        self.assertEqual(options.codex_home, "/tmp/codex-home")
        self.assertEqual(options.auth_file, "/tmp/codex-home/auth.json")
        self.assertEqual(options.max_tokens, 64000)
        self.assertEqual(options.chunk_size, 64000)

    def test_resolve_translate_options_defaults_chunk_size_to_provider_max_tokens(self) -> None:
        options = resolve_translate_options(
            SimpleNamespace(
                input="README.md",
                language="Chinese",
                output=None,
                output_dir="",
                provider="deepseek",
                model="deepseek-chat",
                base_url="",
                api_key="",
                api_key_env="",
                codex_home="",
                auth_file="",
                api_mode="chat_completions",
                chunk_size=None,
                chunk_sleep_seconds=None,
                timeout_sec=None,
                max_tokens=None,
                temperature=None,
                max_retries=None,
                retry_base_delay=None,
                flat=None,
                suffix="zh",
                force=None,
            ),
            load_config(),
        )

        self.assertEqual(options.max_tokens, 8192)
        self.assertEqual(options.chunk_size, 8192)

    def test_resolve_estimate_options_defaults_chunk_size_to_max_tokens(self) -> None:
        options = resolve_estimate_options(
            SimpleNamespace(
                input="README.md",
                language="Chinese",
                output=None,
                output_dir="",
                provider="openai",
                model="gpt-4.1-mini",
                chunk_size=None,
                max_tokens=32000,
                flat=None,
                suffix="zh",
                force=None,
            ),
            load_config(),
        )

        self.assertEqual(options.max_tokens, 32000)
        self.assertEqual(options.chunk_size, 32000)
