import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mdtomd.translator import MarkdownTranslationResult, MarkdownTranslator, TranslateFilesOptions


class MarkdownTranslatorTests(TestCase):
    def setUp(self) -> None:
        self.llm_client = mock.Mock()
        self.translator = MarkdownTranslator(self.llm_client, chunk_sleep_seconds=0.0)

    def test_split_into_chunks_keeps_order(self) -> None:
        content = "alpha\nbeta\ngamma"
        chunks = self.translator.split_into_chunks(content, max_chunk_size=3)
        self.assertEqual(chunks, ["alpha\nbeta", "gamma"])

    def test_split_into_chunks_uses_tokens_instead_of_chars(self) -> None:
        class FakeTokenCounter:
            encoding_name = "fake"
            approximate = False

            def count_text(self, text: str) -> int:
                return len(text.split())

        content = (
            f"{'x' * 100} {'y' * 100} {'z' * 100}\n"
            f"{'m' * 100} {'n' * 100} {'p' * 100}"
        )

        with mock.patch("mdtomd.translator.TokenCounter.for_model", return_value=FakeTokenCounter()):
            chunks = self.translator.split_into_chunks(content, max_chunk_size=6)

        self.assertEqual(chunks, [content])

    def test_translate_markdown_reports_progress(self) -> None:
        progress = []

        with mock.patch.object(
            self.translator,
            "_translate_chunk_with_response",
            side_effect=[
                ("uno", mock.Mock(prompt_tokens=5, completion_tokens=7, total_tokens=12)),
                ("dos", mock.Mock(prompt_tokens=6, completion_tokens=8, total_tokens=14)),
            ],
        ) as translate_chunk:
            translated = self.translator.translate_markdown(
                "aaaa\nbbbb",
                "Spanish",
                progress_callback=lambda chunk, total: progress.append((chunk, total)),
                chunk_size=1,
            )

        self.assertEqual(progress, [(1, 2), (2, 2)])
        self.assertEqual(translated, "uno\n\ndos\n")
        translate_chunk.assert_has_calls(
            [
                mock.call("aaaa", "Spanish"),
                mock.call("bbbb", "Spanish"),
            ]
        )

    def test_translate_markdown_with_stats_accumulates_usage(self) -> None:
        with mock.patch.object(
            self.translator,
            "_translate_chunk_with_response",
            side_effect=[
                ("uno", mock.Mock(prompt_tokens=5, completion_tokens=7, total_tokens=12)),
                ("dos", mock.Mock(prompt_tokens=6, completion_tokens=8, total_tokens=14)),
            ],
        ):
            result = self.translator.translate_markdown_with_stats(
                "aaaa\nbbbb",
                "Spanish",
                chunk_size=1,
            )

        self.assertEqual(result.content, "uno\n\ndos\n")
        self.assertEqual(result.chunk_count, 2)
        self.assertEqual(result.prompt_tokens, 11)
        self.assertEqual(result.completion_tokens, 15)
        self.assertEqual(result.total_tokens, 26)

    def test_translate_chunk_uses_llm_client(self) -> None:
        self.llm_client.chat.return_value = mock.Mock(content="# Titulo")

        translated = self.translator.translate_chunk("# Title", "Spanish")

        self.assertEqual(translated, "# Titulo")
        _, kwargs = self.llm_client.chat.call_args
        self.assertIn("professional markdown translator", kwargs["system"])

    def test_translate_chunk_strips_leading_think_block(self) -> None:
        self.llm_client.chat.return_value = mock.Mock(content="<think>internal reasoning</think>\n\n# 标题")

        translated = self.translator.translate_chunk("# Title", "Chinese")

        self.assertEqual(translated, "# 标题")

    def test_estimate_markdown_tokens_counts_request_tokens(self) -> None:
        estimate = self.translator.estimate_markdown_tokens(
            "# Title\n\nHello world.\n",
            "Chinese",
            chunk_size=100,
            model="gpt-4.1-mini",
        )

        self.assertEqual(estimate.chunk_count, 1)
        self.assertGreater(estimate.source_chars, 0)
        self.assertGreater(estimate.source_tokens, 0)
        self.assertGreater(estimate.request_input_tokens, estimate.source_tokens)
        self.assertTrue(estimate.tokenizer)

    def test_translate_markdown_uses_llm_model_for_chunking(self) -> None:
        class FakeTokenCounter:
            def count_text(self, text: str) -> int:
                return 1

        self.llm_client.config.model = "gpt-4.1-mini"

        with mock.patch("mdtomd.translator.TokenCounter.for_model", return_value=FakeTokenCounter()) as for_model:
            with mock.patch.object(
                self.translator,
                "_translate_chunk_with_response",
                return_value=("uno", mock.Mock(prompt_tokens=1, completion_tokens=1, total_tokens=2)),
            ):
                self.translator.translate_markdown("alpha", "Spanish", chunk_size=10)

        self.assertEqual(for_model.call_args.args[0], "gpt-4.1-mini")

    def test_translate_file_writes_output(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "sample.md"
            output_path = temp_path / "out" / "sample_zh.md"
            input_path.write_text("# Title\n", encoding="utf-8")

            mocked_estimate = mock.Mock(
                source_tokens=12,
                request_input_tokens=20,
                tokenizer="o200k_base",
                approximate=False,
            )
            mocked_translation = MarkdownTranslationResult(
                content="# 标题\n",
                chunk_count=1,
                prompt_tokens=18,
                completion_tokens=10,
                total_tokens=28,
            )
            with mock.patch.object(self.translator, "estimate_markdown_tokens", return_value=mocked_estimate):
                with mock.patch.object(self.translator, "translate_markdown_with_stats", return_value=mocked_translation):
                    result = self.translator.translate_file(input_path, output_path, "Chinese")

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "# 标题\n")
            self.assertEqual(result["outputPath"], str(output_path))
            self.assertEqual(result["requestInputTokens"], 20)
            self.assertEqual(result["completionTokens"], 10)

    def test_translate_files_preserves_structure(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            docs_dir = temp_path / "docs"
            nested_dir = docs_dir / "nested"
            docs_dir.mkdir()
            nested_dir.mkdir()

            (docs_dir / "a.md").write_text("# A\n", encoding="utf-8")
            (nested_dir / "b.mdx").write_text("# B\n", encoding="utf-8")
            (nested_dir / "ignore.txt").write_text("skip\n", encoding="utf-8")

            mocked_translation = MarkdownTranslationResult(
                content="译文\n",
                chunk_count=1,
                prompt_tokens=8,
                completion_tokens=6,
                total_tokens=14,
            )
            mocked_estimate = mock.Mock(
                source_tokens=5,
                request_input_tokens=9,
                tokenizer="o200k_base",
                approximate=False,
            )
            with mock.patch.object(self.translator, "estimate_markdown_tokens", return_value=mocked_estimate):
                with mock.patch.object(self.translator, "translate_markdown_with_stats", return_value=mocked_translation):
                    results = self.translator.translate_files(
                        str(docs_dir / "**/*"),
                        temp_path / "out",
                        "Chinese",
                        options=TranslateFilesOptions(
                            preserve_structure=True,
                            suffix="zh",
                        ),
                    )

            output_paths = {
                Path(item["outputPath"]).relative_to(temp_path / "out")
                for item in results
                if not item.get("error")
            }
            self.assertEqual(output_paths, {Path("a_zh.md"), Path("nested/b_zh.mdx")})
            self.assertEqual(len(results), 2)

    def test_translate_files_skips_up_to_date_outputs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            docs_dir = temp_path / "docs"
            docs_dir.mkdir()

            input_path = docs_dir / "a.md"
            input_path.write_text("# A\n", encoding="utf-8")
            output_dir = temp_path / "out"
            output_dir.mkdir()
            output_path = output_dir / "a_zh.md"
            output_path.write_text("# 甲\n", encoding="utf-8")

            input_stat = input_path.stat()
            os.utime(output_path, (input_stat.st_atime + 10, input_stat.st_mtime + 10))

            with mock.patch.object(self.translator, "translate_markdown") as translate_markdown:
                results = self.translator.translate_files(
                    str(docs_dir / "*.md"),
                    output_dir,
                    "Chinese",
                    options=TranslateFilesOptions(suffix="zh"),
                )

            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]["skipped"])
            self.assertEqual(results[0]["reason"], "up-to-date")
            translate_markdown.assert_not_called()

    def test_translate_files_uses_language_suffix_when_suffix_empty(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            docs_dir = temp_path / "docs"
            docs_dir.mkdir()

            input_path = docs_dir / "a.md"
            input_path.write_text("# A\n", encoding="utf-8")

            mocked_translation = MarkdownTranslationResult(
                content="译文\n",
                chunk_count=1,
                prompt_tokens=8,
                completion_tokens=6,
                total_tokens=14,
            )
            mocked_estimate = mock.Mock(
                source_tokens=5,
                request_input_tokens=9,
                tokenizer="o200k_base",
                approximate=False,
            )
            with mock.patch.object(self.translator, "estimate_markdown_tokens", return_value=mocked_estimate):
                with mock.patch.object(self.translator, "translate_markdown_with_stats", return_value=mocked_translation):
                    results = self.translator.translate_files(
                        str(docs_dir / "*.md"),
                        temp_path / "out",
                        "Chinese",
                    )

            self.assertEqual(Path(results[0]["outputPath"]).name, "a_chinese.md")

    def test_translate_files_skips_translated_inputs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            docs_dir = temp_path / "docs"
            docs_dir.mkdir()

            (docs_dir / "a.md").write_text("# A\n", encoding="utf-8")
            (docs_dir / "a_zh.md").write_text("# 甲\n", encoding="utf-8")

            mocked_translation = MarkdownTranslationResult(
                content="译文\n",
                chunk_count=1,
                prompt_tokens=8,
                completion_tokens=6,
                total_tokens=14,
            )
            mocked_estimate = mock.Mock(
                source_tokens=5,
                request_input_tokens=9,
                tokenizer="o200k_base",
                approximate=False,
            )
            with mock.patch.object(self.translator, "estimate_markdown_tokens", return_value=mocked_estimate):
                with mock.patch.object(self.translator, "translate_markdown_with_stats", return_value=mocked_translation) as translate_markdown:
                    results = self.translator.translate_files(
                        str(docs_dir / "*.md"),
                        temp_path / "out",
                        "Chinese",
                        options=TranslateFilesOptions(suffix="zh"),
                    )

            self.assertEqual(len(results), 1)
            self.assertEqual(Path(results[0]["inputPath"]).name, "a.md")
            self.assertEqual(translate_markdown.call_count, 1)

    def test_estimate_files_tokens_skips_up_to_date_outputs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            docs_dir = temp_path / "docs"
            docs_dir.mkdir()

            input_path = docs_dir / "a.md"
            input_path.write_text("# A\n", encoding="utf-8")
            output_dir = temp_path / "out"
            output_dir.mkdir()
            output_path = output_dir / "a_zh.md"
            output_path.write_text("# 甲\n", encoding="utf-8")

            input_stat = input_path.stat()
            os.utime(output_path, (input_stat.st_atime + 10, input_stat.st_mtime + 10))

            estimate = self.translator.estimate_files_tokens(
                str(docs_dir / "*.md"),
                output_dir,
                "Chinese",
                options=TranslateFilesOptions(suffix="zh"),
                model="gpt-4.1-mini",
            )

            self.assertEqual(estimate.file_count, 1)
            self.assertEqual(estimate.pending_file_count, 0)
            self.assertEqual(estimate.skipped_file_count, 1)
            self.assertEqual(estimate.request_input_tokens, 0)
