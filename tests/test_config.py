import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mdtomd.config import load_config


class ConfigTests(TestCase):
    def test_load_config_allows_blank_llm_max_tokens(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "llm:",
                        "  provider: deepseek",
                        "  max_tokens:",
                        "providers:",
                        "  deepseek:",
                        "    model: deepseek-chat",
                        "    max_tokens: 8192",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(str(config_path))

        self.assertEqual(config.llm.provider, "deepseek")
        self.assertEqual(config.llm.max_tokens, 8192)
        self.assertEqual(config.providers["deepseek"].max_tokens, 8192)

    def test_load_config_allows_blank_translator_chunk_size(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "translator:",
                        "  chunk_size:",
                        "  chunk_sleep_seconds: 0.5",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(str(config_path))

        self.assertIsNone(config.translator.chunk_size)

    def test_load_config_parses_nested_yaml(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "llm:",
                        "  provider: openrouter",
                        "  model: google/gemini-2.5-flash-lite",
                        "  timeout_sec: 90",
                        "providers:",
                        "  openai-codex:",
                        "    model: gpt-5.4-mini",
                        "    api_key: codex-test-token",
                        "    codex_home: /tmp/codex-home",
                        "    auth_file: /tmp/codex-home/auth.json",
                        "translator:",
                        "  chunk_size: 6000",
                        "  chunk_sleep_seconds: 0.0",
                        "defaults:",
                        "  language: Chinese",
                        "  suffix: zh",
                        "  flat: false",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(str(config_path))

        self.assertEqual(config.llm.provider, "openrouter")
        self.assertEqual(config.llm.model, "google/gemini-2.5-flash-lite")
        self.assertEqual(config.llm.timeout_sec, 90.0)
        self.assertEqual(config.providers["openai-codex"].model, "gpt-5.4-mini")
        self.assertEqual(config.providers["openai-codex"].api_key, "codex-test-token")
        self.assertEqual(config.providers["openai-codex"].codex_home, "/tmp/codex-home")
        self.assertEqual(config.providers["openai-codex"].auth_file, "/tmp/codex-home/auth.json")
        self.assertEqual(config.translator.chunk_size, 6000)
        self.assertEqual(config.translator.chunk_sleep_seconds, 0.0)
        self.assertEqual(config.defaults.language, "Chinese")
        self.assertEqual(config.defaults.suffix, "zh")

    def test_load_config_parses_featured_models(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "display:",
                        "  featured_models:",
                        "    openai-gpt-4.1-mini:",
                        "      provider: openai",
                        "      model: gpt-4.1-mini",
                        "      label: OpenAI GPT-4.1 Mini",
                        "    deepseek-chat:",
                        "      provider: deepseek",
                        "      model: deepseek-chat",
                        "      label: DeepSeek Chat",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(str(config_path))

        self.assertEqual(config.display.featured_models["openai-gpt-4.1-mini"].provider, "openai")
        self.assertEqual(config.display.featured_models["openai-gpt-4.1-mini"].model, "gpt-4.1-mini")
        self.assertEqual(config.display.featured_models["deepseek-chat"].label, "DeepSeek Chat")
