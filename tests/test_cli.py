import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mdtomd import cli
from mdtomd.translator import BatchTokenEstimate, FileTokenEstimate


class CliTests(TestCase):
    def test_languages_command(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = cli.main(["languages"])

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Spanish", output)
        self.assertIn("Chinese", output)

    def test_translate_single_file_uses_default_suffix(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "sample.md"
            input_path.write_text("# Title\n", encoding="utf-8")
            empty_config = temp_path / "empty.yaml"
            empty_config.write_text("", encoding="utf-8")

            mocked_result = {
                "inputPath": str(input_path),
                "outputPath": str(temp_path / "sample_chinese.md"),
                "targetLanguage": "Chinese",
                "chunkCount": 1,
                "sourceTokens": 12,
                "requestInputTokens": 20,
                "completionTokens": 10,
                "totalTokens": 30,
                "originalLength": 8,
                "translatedLength": 8,
            }

            buffer = io.StringIO()
            mocked_client = mock.Mock()
            mocked_client.config.provider = "openai"
            mocked_client.config.model = "gpt-4.1-mini"
            with mock.patch.object(cli.MarkdownTranslator, "translate_file", return_value=mocked_result) as translate_file:
                with mock.patch.object(cli, "create_llm_client", return_value=mocked_client):
                    with redirect_stdout(buffer):
                        exit_code = cli.main(
                            [
                                "translate",
                                "--config",
                                str(empty_config),
                                "-i",
                                str(input_path),
                                "-l",
                                "Chinese",
                                "--provider",
                                "openai",
                                "-k",
                                "test-key",
                            ]
                        )

            self.assertEqual(exit_code, 0)
            translate_args = translate_file.call_args.args
            self.assertEqual(Path(translate_args[1]), temp_path / "sample_chinese.md")
            self.assertIn("请求输入 tokens: 20", buffer.getvalue())
            self.assertIn("回复输出 tokens: 10", buffer.getvalue())

    def test_translate_single_file_skips_translated_input(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "sample_zh.md"
            input_path.write_text("# 标题\n", encoding="utf-8")
            empty_config = temp_path / "empty.yaml"
            empty_config.write_text("", encoding="utf-8")

            buffer = io.StringIO()
            mocked_client = mock.Mock()
            mocked_client.config.provider = "openai"
            mocked_client.config.model = "gpt-4.1-mini"
            with mock.patch.object(cli, "create_llm_client", return_value=mocked_client):
                with mock.patch.object(cli.MarkdownTranslator, "translate_file") as translate_file:
                    with redirect_stdout(buffer):
                        exit_code = cli.main(
                            [
                                "translate",
                                "--config",
                                str(empty_config),
                                "-i",
                                str(input_path),
                                "-l",
                                "Chinese",
                                "--provider",
                                "openai",
                                "-k",
                                "test-key",
                                "--suffix",
                                "zh",
                            ]
                        )

            self.assertEqual(exit_code, 0)
            self.assertIn("跳过已翻译输入", buffer.getvalue())
            translate_file.assert_not_called()

    def test_translate_single_file_skips_up_to_date_output(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "sample.md"
            input_path.write_text("# Title\n", encoding="utf-8")
            output_path = temp_path / "sample_zh.md"
            output_path.write_text("# 标题\n", encoding="utf-8")
            input_stat = input_path.stat()
            os.utime(output_path, (input_stat.st_atime + 10, input_stat.st_mtime + 10))
            empty_config = temp_path / "empty.yaml"
            empty_config.write_text("", encoding="utf-8")

            buffer = io.StringIO()
            mocked_client = mock.Mock()
            mocked_client.config.provider = "openai"
            mocked_client.config.model = "gpt-4.1-mini"
            with mock.patch.object(cli, "create_llm_client", return_value=mocked_client):
                with mock.patch.object(cli.MarkdownTranslator, "translate_file") as translate_file:
                    with redirect_stdout(buffer):
                        exit_code = cli.main(
                            [
                                "translate",
                                "--config",
                                str(empty_config),
                                "-i",
                                str(input_path),
                                "-l",
                                "Chinese",
                                "--provider",
                                "openai",
                                "-k",
                                "test-key",
                                "--suffix",
                                "zh",
                            ]
                        )

            self.assertEqual(exit_code, 0)
            self.assertIn("跳过已是最新输出", buffer.getvalue())
            translate_file.assert_not_called()

    def test_translate_batch_requires_output_dir(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = cli.main(
                [
                    "translate",
                    "-i",
                    "*.md",
                    "-l",
                    "Chinese",
                    "--provider",
                    "openai",
                    "-k",
                    "test-key",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("--output-dir", buffer.getvalue())

    def test_translate_batch_defaults_to_incremental_skip(self) -> None:
        buffer = io.StringIO()
        mocked_translator = mock.Mock()
        mocked_translator.translate_files.return_value = [
            {"inputPath": "a.md", "outputPath": "a_zh.md", "skipped": True, "success": True, "reason": "up-to-date"}
        ]
        mocked_client = mock.Mock()
        mocked_client.config.provider = "openrouter"
        mocked_client.config.model = "google/gemini-2.5-flash-lite"

        args = SimpleNamespace(
            config=None,
            input="docs/*.md",
            language="Chinese",
            output=None,
            output_dir="out",
            api_key="test-key",
            provider="auto",
            model="",
            base_url="",
            api_key_env="",
            api_mode="auto",
            flat=False,
            suffix="zh",
            force=False,
        )

        with mock.patch.object(cli, "glob") as glob_module:
            glob_module.glob.return_value = ["docs/a.md"]
            with mock.patch.object(cli, "create_llm_client", return_value=mocked_client):
                with mock.patch.object(cli, "MarkdownTranslator", return_value=mocked_translator):
                    with redirect_stdout(buffer):
                        exit_code = cli._handle_translate(args)

        self.assertEqual(exit_code, 0)
        options = mocked_translator.translate_files.call_args.kwargs["options"]
        self.assertTrue(options.skip_existing)
        self.assertTrue(options.skip_translated_inputs)
        self.assertIn("跳过: 1", buffer.getvalue())

    def test_translate_directory_defaults_output_dir_to_input_dir(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            docs_dir = temp_path / "docs"
            docs_dir.mkdir()
            (docs_dir / "a.md").write_text("# A\n", encoding="utf-8")
            empty_config = temp_path / "empty.yaml"
            empty_config.write_text("", encoding="utf-8")

            mocked_translator = mock.Mock()
            mocked_translator.translate_files.return_value = []
            mocked_client = mock.Mock()
            mocked_client.config.provider = "deepseek"
            mocked_client.config.model = "deepseek-chat"

            with mock.patch.object(cli, "create_llm_client", return_value=mocked_client):
                with mock.patch.object(cli, "MarkdownTranslator", return_value=mocked_translator):
                    exit_code = cli.main(
                        [
                            "translate",
                            "--config",
                            str(empty_config),
                            "-i",
                            str(docs_dir),
                            "-l",
                            "Chinese",
                            "--provider",
                            "deepseek",
                            "-k",
                            "test-key",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            call_args = mocked_translator.translate_files.call_args.args
            self.assertEqual(call_args[0], str(docs_dir.resolve() / "**/*"))
            self.assertEqual(call_args[1], str(docs_dir.resolve()))

    def test_estimate_directory_defaults_output_dir_to_input_dir(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            docs_dir = temp_path / "docs"
            docs_dir.mkdir()
            (docs_dir / "a.md").write_text("# A\n", encoding="utf-8")
            empty_config = temp_path / "empty.yaml"
            empty_config.write_text("", encoding="utf-8")

            mocked_estimate = BatchTokenEstimate(
                file_count=1,
                pending_file_count=1,
                skipped_file_count=0,
                chunk_count=1,
                source_chars=10,
                source_tokens=4,
                request_input_tokens=8,
                tokenizer="o200k_base",
                approximate=False,
                files=[FileTokenEstimate(str(docs_dir / "a.md"), str(docs_dir / "a_zh.md"), chunk_count=1, source_chars=10, source_tokens=4, request_input_tokens=8)],
            )

            with mock.patch.object(cli.MarkdownTranslator, "estimate_files_tokens", return_value=mocked_estimate) as estimate_files_tokens:
                exit_code = cli.main(
                    [
                        "estimate",
                        "--config",
                        str(empty_config),
                        "-i",
                        str(docs_dir),
                        "-l",
                        "Chinese",
                        "--provider",
                        "deepseek",
                    ]
                )

            self.assertEqual(exit_code, 0)
            call_args = estimate_files_tokens.call_args.args
            self.assertEqual(call_args[0], str(docs_dir.resolve() / "**/*"))
            self.assertEqual(call_args[1], str(docs_dir.resolve()))

    def test_providers_command(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = cli.main(["providers"])

        self.assertEqual(exit_code, 0)
        self.assertIn("openai", buffer.getvalue())

    def test_models_command_uses_configured_featured_models(self) -> None:
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
                        "    anthropic-claude-3-5-sonnet:",
                        "      provider: anthropic",
                        "      model: claude-3-5-sonnet-latest",
                        "      label: Claude 3.5 Sonnet",
                    ]
                ),
                encoding="utf-8",
            )

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = cli.main(["models", "--config", str(config_path)])

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("OpenAI GPT-4.1 Mini", output)
        self.assertIn("Claude 3.5 Sonnet", output)
        self.assertIn("USD in=0.4/MTokens out=1.6/MTokens", output)

    def test_translate_uses_config_defaults(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "sample.md"
            input_path.write_text("# Title\n", encoding="utf-8")
            config_path = temp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "llm:",
                        "  provider: openai",
                        "defaults:",
                        "  language: Chinese",
                        "  suffix: zh",
                    ]
                ),
                encoding="utf-8",
            )

            mocked_result = {
                "inputPath": str(input_path),
                "outputPath": str(temp_path / "sample_zh.md"),
                "targetLanguage": "Chinese",
                "chunkCount": 1,
                "sourceTokens": 12,
                "requestInputTokens": 20,
                "completionTokens": 10,
                "totalTokens": 30,
                "originalLength": 8,
                "translatedLength": 8,
            }
            mocked_client = mock.Mock()
            mocked_client.config.provider = "openai"
            mocked_client.config.model = "gpt-4.1-mini"

            buffer = io.StringIO()
            with mock.patch.object(cli, "create_llm_client", return_value=mocked_client):
                with mock.patch.object(cli.MarkdownTranslator, "translate_file", return_value=mocked_result) as translate_file:
                    with redirect_stdout(buffer):
                        exit_code = cli.main(
                            [
                                "translate",
                                "--config",
                                str(config_path),
                                "-i",
                                str(input_path),
                            ]
                        )

            self.assertEqual(exit_code, 0)
            translate_args = translate_file.call_args.args
            self.assertEqual(translate_args[2], "Chinese")

    def test_translate_uses_provider_override_from_config(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "sample.md"
            input_path.write_text("# Title\n", encoding="utf-8")
            config_path = temp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "llm:",
                        "  provider: openrouter",
                        "providers:",
                        "  openrouter:",
                        "    model: google/gemini-2.5-flash-lite",
                        "    api_key: or-test-key",
                        "defaults:",
                        "  language: Chinese",
                    ]
                ),
                encoding="utf-8",
            )

            mocked_result = {
                "inputPath": str(input_path),
                "outputPath": str(temp_path / "sample_chinese.md"),
                "targetLanguage": "Chinese",
                "originalLength": 8,
                "translatedLength": 8,
            }
            mocked_client = mock.Mock()
            mocked_client.config.provider = "openrouter"
            mocked_client.config.model = "google/gemini-2.5-flash-lite"

            with mock.patch.object(cli, "create_llm_client", return_value=mocked_client) as create_llm_client:
                with mock.patch.object(cli.MarkdownTranslator, "translate_file", return_value=mocked_result):
                    exit_code = cli.main(
                        [
                            "translate",
                            "--config",
                            str(config_path),
                            "-i",
                            str(input_path),
                        ]
                    )

            self.assertEqual(exit_code, 0)
            self.assertEqual(create_llm_client.call_args.kwargs["provider"], "openrouter")
            self.assertEqual(create_llm_client.call_args.kwargs["model"], "google/gemini-2.5-flash-lite")
            self.assertEqual(create_llm_client.call_args.kwargs["api_key"], "or-test-key")

    def test_estimate_single_file_prints_token_summary(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "sample.md"
            input_path.write_text("# Title\n", encoding="utf-8")
            config_path = temp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "llm:",
                        "  provider: openai",
                        "defaults:",
                        "  language: Chinese",
                        "  suffix: zh",
                    ]
                ),
                encoding="utf-8",
            )

            buffer = io.StringIO()
            mocked_estimate = FileTokenEstimate(
                input_path=str(input_path),
                output_path=str(temp_path / "sample_zh.md"),
                chunk_count=2,
                source_chars=100,
                source_tokens=40,
                request_input_tokens=60,
            )
            mocked_markdown_estimate = mock.Mock(tokenizer="o200k_base", approximate=False)
            with mock.patch.object(cli.MarkdownTranslator, "estimate_file_tokens", return_value=mocked_estimate):
                with mock.patch.object(cli.MarkdownTranslator, "estimate_markdown_tokens", return_value=mocked_markdown_estimate):
                    with redirect_stdout(buffer):
                        exit_code = cli.main(
                            [
                                "estimate",
                                "--config",
                                str(config_path),
                                "-i",
                                str(input_path),
                            ]
                        )

            output = buffer.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("统计模式: 单文件", output)
            self.assertIn("请求输入 tokens: 60", output)
            self.assertIn("价格:", output)
            self.assertIn("预计输入成本:", output)
            self.assertIn("推荐模型费用:", output)
            self.assertIn("OpenAI GPT-4.1 Mini", output)

    def test_estimate_single_file_skips_up_to_date_output(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "sample.md"
            input_path.write_text("# Title\n", encoding="utf-8")
            output_path = temp_path / "sample_zh.md"
            output_path.write_text("# 标题\n", encoding="utf-8")
            input_stat = input_path.stat()
            os.utime(output_path, (input_stat.st_atime + 10, input_stat.st_mtime + 10))
            config_path = temp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "llm:",
                        "  provider: openai",
                        "defaults:",
                        "  language: Chinese",
                        "  suffix: zh",
                    ]
                ),
                encoding="utf-8",
            )

            buffer = io.StringIO()
            with mock.patch.object(cli.MarkdownTranslator, "estimate_file_tokens") as estimate_file_tokens:
                with redirect_stdout(buffer):
                    exit_code = cli.main(
                        [
                            "estimate",
                            "--config",
                            str(config_path),
                            "-i",
                            str(input_path),
                        ]
                    )

            output = buffer.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("跳过已是最新输出", output)
            estimate_file_tokens.assert_not_called()

    def test_estimate_batch_uses_output_dir_and_prints_summary(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "llm:",
                        "  provider: openrouter",
                        "providers:",
                        "  openrouter:",
                        "    model: google/gemini-2.5-flash-lite",
                        "defaults:",
                        "  language: Chinese",
                    ]
                ),
                encoding="utf-8",
            )

            estimate = BatchTokenEstimate(
                file_count=3,
                pending_file_count=2,
                skipped_file_count=1,
                chunk_count=8,
                source_chars=2400,
                source_tokens=900,
                request_input_tokens=1100,
                tokenizer="o200k_base",
                approximate=False,
                files=[
                    FileTokenEstimate("a.md", "out/a_zh.md", chunk_count=5, source_chars=1200, source_tokens=500, request_input_tokens=620),
                    FileTokenEstimate("b.md", "out/b_zh.md", chunk_count=3, source_chars=1200, source_tokens=400, request_input_tokens=480),
                    FileTokenEstimate("c.md", "out/c_zh.md", skipped=True, reason="up-to-date"),
                ],
            )

            buffer = io.StringIO()
            with mock.patch.object(cli, "glob") as glob_module:
                glob_module.glob.return_value = ["docs/a.md", "docs/b.md"]
                with mock.patch.object(cli.MarkdownTranslator, "estimate_files_tokens", return_value=estimate):
                    with redirect_stdout(buffer):
                        exit_code = cli.main(
                            [
                                "estimate",
                                "--config",
                                str(config_path),
                                "-i",
                                "docs/*.md",
                                "-d",
                                "out",
                            ]
                        )

            output = buffer.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("统计模式: 批量", output)
            self.assertIn("待翻译文件: 2", output)
            self.assertIn("请求输入 tokens: 1100", output)
            self.assertIn("推荐模型费用:", output)
            self.assertIn("OpenAI GPT-4.1 Mini", output)
            self.assertIn("a.md chunks=5", output)
