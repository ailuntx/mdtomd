from __future__ import annotations

import argparse
import glob
from pathlib import Path
from typing import Optional, Sequence

from .config import load_config
from .llm import create_llm_client, list_supported_providers
from .options import resolve_estimate_options, resolve_translate_options
from .paths import (
    contains_glob,
    is_directory_input,
    is_translated_input,
    resolve_directory_input_pattern,
    resolve_effective_suffix,
    resolve_single_output_path,
    should_skip_existing,
)
from .pricing import lookup_model_price
from .reporting import build_featured_price_summary, build_price_summary, format_price_brief, get_featured_models
from .translator import MarkdownTranslator, TranslateFilesOptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdtomd",
        description="Translate markdown files with multiple LLM providers",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    translate_parser = subparsers.add_parser("translate", help="Translate markdown files")
    _add_shared_config_arg(translate_parser)
    _add_shared_input_arg(translate_parser)
    translate_parser.add_argument("-l", "--language", help="Target language")
    translate_parser.add_argument("-o", "--output", help="Output file path for single file translation")
    translate_parser.add_argument("-d", "--output-dir", help="Output directory for batch translation or single file translation")
    translate_parser.add_argument("-k", "--api-key", "--key", dest="api_key", help="API key for the selected provider")
    translate_parser.add_argument("-p", "--provider", help="Provider name, such as auto/openai/openai-codex/openrouter/anthropic/gemini/deepseek/minimax/kimi/openai-compatible")
    translate_parser.add_argument("-m", "--model", help="Override model name")
    translate_parser.add_argument("--base-url", help="Override API base URL, mainly for openai-compatible/custom endpoints")
    translate_parser.add_argument("--api-key-env", help="Read API key from the specified environment variable")
    translate_parser.add_argument("--api-mode", choices=("auto", "chat_completions", "responses"), help="OpenAI transport mode")
    translate_parser.add_argument("--chunk-size", type=int, help="Override markdown chunk size")
    translate_parser.add_argument("--chunk-sleep-seconds", type=float, help="Sleep interval between chunk requests")
    translate_parser.add_argument("--timeout-sec", type=float, help="LLM request timeout")
    translate_parser.add_argument("--max-tokens", type=int, help="LLM max output tokens")
    translate_parser.add_argument("--temperature", type=float, help="LLM sampling temperature")
    translate_parser.add_argument("--max-retries", type=int, help="LLM retry count")
    translate_parser.add_argument("--retry-base-delay", type=float, help="Base retry delay in seconds")
    translate_parser.add_argument("--flat", action=argparse.BooleanOptionalAction, default=None, help="Use flat output structure in batch mode")
    translate_parser.add_argument("--suffix", help="Custom suffix for output files")
    translate_parser.add_argument("--force", action=argparse.BooleanOptionalAction, default=None, help="Ignore incremental skip and re-translate existing outputs")

    estimate_parser = subparsers.add_parser("estimate", help="Estimate pending translation tokens")
    _add_shared_config_arg(estimate_parser)
    _add_shared_input_arg(estimate_parser)
    estimate_parser.add_argument("-l", "--language", help="Target language")
    estimate_parser.add_argument("-o", "--output", help="Output file path for single file estimate")
    estimate_parser.add_argument("-d", "--output-dir", help="Output directory for batch estimate or single file estimate")
    estimate_parser.add_argument("-p", "--provider", help="Provider name, used to select default model and tokenizer")
    estimate_parser.add_argument("-m", "--model", help="Override model name for token estimation")
    estimate_parser.add_argument("--chunk-size", type=int, help="Override markdown chunk size")
    estimate_parser.add_argument("--flat", action=argparse.BooleanOptionalAction, default=None, help="Use flat output structure in batch mode")
    estimate_parser.add_argument("--suffix", help="Custom suffix for output files")
    estimate_parser.add_argument("--force", action=argparse.BooleanOptionalAction, default=None, help="Ignore incremental skip and estimate all matched source files")

    subparsers.add_parser("languages", help="List common supported languages")
    models_parser = subparsers.add_parser("models", help="List featured models")
    _add_shared_config_arg(models_parser)
    subparsers.add_parser("providers", help="List supported LLM providers")
    subparsers.add_parser("setup", help="Show setup guide")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "languages":
        return _handle_languages()
    if args.command == "models":
        return _handle_models(args)
    if args.command == "providers":
        return _handle_providers()
    if args.command == "setup":
        return _handle_setup()
    if args.command == "estimate":
        return _handle_estimate(args)
    return _handle_translate(args)


def _handle_translate(args: argparse.Namespace) -> int:
    try:
        config = load_config(getattr(args, "config", None))
    except Exception as exc:
        print(f"配置文件加载失败: {exc}")
        return 1

    options = resolve_translate_options(args, config)
    if not options.language:
        print("缺少目标语言，请用 --language 或在 config.yaml 的 defaults.language 中设置。")
        return 1

    batch_input, batch_output_dir, is_batch = _resolve_batch_input(options.input, options.output_dir)
    matched_files = glob.glob(batch_input if is_batch else options.input, recursive=True)
    is_pattern = is_batch or contains_glob(options.input) or len(matched_files) > 1

    try:
        llm_client = create_llm_client(**options.llm_kwargs())
    except Exception as exc:
        print(f"LLM 配置失败: {exc}")
        return 1

    translator = MarkdownTranslator(llm_client, chunk_sleep_seconds=options.chunk_sleep_seconds)

    try:
        if is_pattern:
            if not batch_output_dir:
                print("批量翻译需要指定 --output-dir。")
                return 1

            print(f"批量翻译: {batch_input}")
            print(f"输出目录: {Path(batch_output_dir).resolve()}")
            print(f"目标语言: {options.language}")
            print(f"LLM: {llm_client.config.provider} / {llm_client.config.model}")
            if config.path:
                print(f"配置文件: {Path(config.path).resolve()}")

            def batch_progress(file_num: int, total_files: int, chunk: int, total_chunks: int, file_name: str) -> None:
                print(f"[{file_num}/{total_files}] {Path(file_name).name} chunk {chunk}/{total_chunks}")

            results = translator.translate_files(
                batch_input,
                batch_output_dir,
                options.language,
                options=TranslateFilesOptions(
                    progress_callback=batch_progress,
                    preserve_structure=not options.flat,
                    suffix=options.suffix,
                    skip_existing=not options.force,
                ),
                chunk_size=options.chunk_size,
            )
            return _print_translate_batch_summary(results)

        input_path = Path(options.input)
        if not input_path.exists():
            print(f"输入文件不存在: {input_path}")
            return 1
        if not MarkdownTranslator.is_markdown_file(input_path):
            print("输入文件必须是 .md / .markdown / .mdx")
            return 1

        effective_suffix = resolve_effective_suffix(options.suffix, options.language)
        if not options.force and is_translated_input(input_path, effective_suffix):
            print(f"跳过已翻译输入: {input_path}")
            return 0

        output_path = resolve_single_output_path(
            input_path=input_path,
            output=options.output,
            output_dir=options.output_dir,
            suffix=options.suffix,
            language=options.language,
        )
        if not options.force and should_skip_existing(input_path, output_path):
            print(f"跳过已是最新输出: {output_path}")
            return 0

        if output_path.exists():
            print(f"警告: 输出文件已存在，将被覆盖: {output_path}")

        print(f"输入文件: {input_path.resolve()}")
        print(f"输出文件: {output_path.resolve()}")
        print(f"目标语言: {options.language}")
        print(f"LLM: {llm_client.config.provider} / {llm_client.config.model}")
        if config.path:
            print(f"配置文件: {Path(config.path).resolve()}")

        result = translator.translate_file(
            input_path,
            output_path,
            options.language,
            progress_callback=lambda chunk, total: print(f"chunk {chunk}/{total}"),
            chunk_size=options.chunk_size,
        )
        if "chunkCount" in result:
            print(f"分块数: {result['chunkCount']}")
        if "sourceTokens" in result:
            print(f"原文 tokens: {result['sourceTokens']}")
        if "requestInputTokens" in result:
            print(f"请求输入 tokens: {result['requestInputTokens']}")
        if "completionTokens" in result:
            print(f"回复输出 tokens: {result['completionTokens']}")
        print(f"原文长度: {result['originalLength']}")
        print(f"译文长度: {result['translatedLength']}")
        print(f"已写入: {result['outputPath']}")
        return 0
    except Exception as exc:
        print(f"翻译失败: {exc}")
        return 1


def _handle_estimate(args: argparse.Namespace) -> int:
    try:
        config = load_config(getattr(args, "config", None))
    except Exception as exc:
        print(f"配置文件加载失败: {exc}")
        return 1

    options = resolve_estimate_options(args, config)
    if not options.language:
        print("缺少目标语言，请用 --language 或在 config.yaml 的 defaults.language 中设置。")
        return 1

    translator = MarkdownTranslator(None, chunk_sleep_seconds=0.0)
    batch_input, batch_output_dir, is_batch = _resolve_batch_input(options.input, options.output_dir)
    matched_files = glob.glob(batch_input if is_batch else options.input, recursive=True)
    is_pattern = is_batch or contains_glob(options.input) or len(matched_files) > 1

    try:
        if is_pattern:
            if not batch_output_dir:
                print("批量统计需要指定 --output-dir，用于判断哪些文件会被跳过。")
                return 1

            estimate = translator.estimate_files_tokens(
                batch_input,
                batch_output_dir,
                options.language,
                options=TranslateFilesOptions(
                    preserve_structure=not options.flat,
                    suffix=options.suffix,
                    skip_existing=not options.force,
                ),
                chunk_size=options.chunk_size,
                model=options.resolved_model,
            )

            print("统计模式: 批量")
            print(f"输入模式: {batch_input}")
            print(f"输出目录: {Path(batch_output_dir).resolve()}")
            print(f"目标语言: {options.language}")
            print(f"模型: {options.provider or 'auto'} / {options.resolved_model or '-'}")
            print(f"tokenizer: {estimate.tokenizer}{' (近似)' if estimate.approximate else ''}")
            print(f"文件总数: {estimate.file_count}")
            print(f"待翻译文件: {estimate.pending_file_count}")
            print(f"跳过文件: {estimate.skipped_file_count}")
            print(f"分块总数: {estimate.chunk_count}")
            print(f"待翻译字符: {estimate.source_chars}")
            print(f"原文 tokens: {estimate.source_tokens}")
            print(f"请求输入 tokens: {estimate.request_input_tokens}")
            _print_lines(
                build_price_summary(
                    provider=options.provider,
                    model=options.resolved_model,
                    input_tokens=estimate.request_input_tokens,
                    approx_output_tokens=estimate.source_tokens,
                )
            )
            _print_lines(
                build_featured_price_summary(
                    config=config,
                    input_tokens=estimate.request_input_tokens,
                    approx_output_tokens=estimate.source_tokens,
                )
            )

            pending_files = [item for item in estimate.files if not item.skipped]
            if pending_files:
                print("高消耗文件:")
                for item in sorted(pending_files, key=lambda current: current.request_input_tokens, reverse=True)[:5]:
                    print(
                        f"- {item.input_path} "
                        f"chunks={item.chunk_count} "
                        f"source_tokens={item.source_tokens} "
                        f"request_tokens={item.request_input_tokens}"
                    )
            return 0

        input_path = Path(options.input)
        if not input_path.exists():
            print(f"输入文件不存在: {input_path}")
            return 1
        if not MarkdownTranslator.is_markdown_file(input_path):
            print("输入文件必须是 .md / .markdown / .mdx")
            return 1

        effective_suffix = resolve_effective_suffix(options.suffix, options.language)
        if not options.force and is_translated_input(input_path, effective_suffix):
            print(f"跳过已翻译输入: {input_path}")
            return 0

        output_path = resolve_single_output_path(
            input_path=input_path,
            output=options.output,
            output_dir=options.output_dir,
            suffix=options.suffix,
            language=options.language,
        )
        if not options.force and should_skip_existing(input_path, output_path):
            print(f"跳过已是最新输出: {output_path}")
            return 0

        estimate = translator.estimate_file_tokens(
            input_path,
            output_path,
            options.language,
            chunk_size=options.chunk_size,
            model=options.resolved_model,
        )
        tokenizer_label = "heuristic"
        approximate = True
        try:
            markdown_estimate = translator.estimate_markdown_tokens(
                input_path.read_text(encoding="utf-8"),
                options.language,
                chunk_size=options.chunk_size,
                model=options.resolved_model,
            )
            tokenizer_label = markdown_estimate.tokenizer
            approximate = markdown_estimate.approximate
        except Exception:
            pass

        print("统计模式: 单文件")
        print(f"输入文件: {input_path.resolve()}")
        print(f"输出文件: {output_path.resolve()}")
        print(f"目标语言: {options.language}")
        print(f"模型: {options.provider or 'auto'} / {options.resolved_model or '-'}")
        print(f"tokenizer: {tokenizer_label}{' (近似)' if approximate else ''}")
        print(f"分块数: {estimate.chunk_count}")
        print(f"原文字符: {estimate.source_chars}")
        print(f"原文 tokens: {estimate.source_tokens}")
        print(f"请求输入 tokens: {estimate.request_input_tokens}")
        _print_lines(
            build_price_summary(
                provider=options.provider,
                model=options.resolved_model,
                input_tokens=estimate.request_input_tokens,
                approx_output_tokens=estimate.source_tokens,
            )
        )
        _print_lines(
            build_featured_price_summary(
                config=config,
                input_tokens=estimate.request_input_tokens,
                approx_output_tokens=estimate.source_tokens,
            )
        )
        return 0
    except Exception as exc:
        print(f"统计失败: {exc}")
        return 1


def _handle_languages() -> int:
    print("常用语言:")
    languages = MarkdownTranslator.get_supported_languages()
    columns = 3
    rows = (len(languages) + columns - 1) // columns
    for row_index in range(rows):
        row_items = []
        for column_index in range(columns):
            item_index = row_index + column_index * rows
            if item_index < len(languages):
                row_items.append(f"{item_index + 1:>2}. {languages[item_index]:<15}")
        print("  ".join(row_items))
    return 0


def _handle_providers() -> int:
    print("支持的 provider:")
    for item in list_supported_providers():
        print(
            f"- {item['id']:<18} "
            f"{item['label']:<20} "
            f"model={item['default_model'] or '-'} "
            f"env={item['api_key_envs']}"
        )
    print("- auto               按常见环境变量自动选择")
    return 0


def _handle_models(args: argparse.Namespace) -> int:
    try:
        config = load_config(getattr(args, "config", None))
    except Exception as exc:
        print(f"配置文件加载失败: {exc}")
        return 1

    print("推荐模型:")
    for item in get_featured_models(config):
        provider = item["provider"]
        model = item["model"]
        label = item["label"] or model
        print(f"- {label} | {provider} / {model} | price={format_price_brief(lookup_model_price(provider, model))}")
    return 0


def _handle_setup() -> int:
    print("1. 先看可用 provider:")
    print("   python -m mdtomd providers")
    print("2. 看内置推荐模型:")
    print("   python -m mdtomd models")
    print("3. 编辑 config.yaml，或设置环境变量，例如:")
    print('   export OPENROUTER_API_KEY="your-key"')
    print('   export OPENAI_API_KEY="your-key"')
    print('   export OPENAI_CODEX_ACCESS_TOKEN="your-token"')
    print('   export ANTHROPIC_API_KEY="your-key"')
    print('   export GEMINI_API_KEY="your-key"')
    print("4. 开始翻译:")
    print("   python -m mdtomd translate -i README.md")
    print("5. 先做 token 统计:")
    print("   python -m mdtomd estimate -i README.md -l Chinese")
    print("6. 如果是自建 OpenAI 兼容接口:")
    print("   python -m mdtomd translate -i README.md --provider openai-compatible --base-url http://localhost:8000/v1 --api-key your-key --model qwen2.5-14b-instruct")
    return 0


def _add_shared_config_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-c", "--config", help="Path to config.yaml, default is ./config.yaml or ./config.yml")


def _add_shared_input_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-i", "--input", required=True, help='Input file path or glob pattern, such as "README.md" or "docs/**/*.md"')


def _print_translate_batch_summary(results: list[dict]) -> int:
    skipped = sum(1 for item in results if item.get("skipped"))
    successful = sum(1 for item in results if not item.get("error") and not item.get("skipped"))
    failed = sum(1 for item in results if item.get("error"))

    print(f"完成: {successful}/{len(results)}")
    if skipped:
        print(f"跳过: {skipped}")
    if failed:
        print(f"失败: {failed}")
        for item in results:
            if item.get("error"):
                print(f"- {item['inputPath']}: {item['error']}")
        return 1
    return 0


def _print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)


def _resolve_batch_input(input_value: str, output_dir: str) -> tuple[str, str, bool]:
    if is_directory_input(input_value):
        directory = str(Path(input_value).resolve())
        return resolve_directory_input_pattern(directory), output_dir or directory, True
    return input_value, output_dir, False
