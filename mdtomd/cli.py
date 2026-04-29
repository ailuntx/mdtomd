from __future__ import annotations

import argparse
import glob
import importlib.metadata
import json
import sys
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
    resolve_existing_output_path,
    resolve_glob_base_dir,
    resolve_single_output_path,
    should_skip_existing,
)
from .pricing import estimate_cost, lookup_model_price
from .reporting import format_price_brief, get_featured_models
from .translator import MarkdownTranslator, TranslateFilesOptions


COMMANDS = {"translate", "estimate", "languages", "models", "providers", "setup", "run"}
PROGRESS_EVENT_PREFIX = "MDTOMD_PROGRESS "
OPTIONS_WITH_VALUE = {
    "-c",
    "--config",
    "-i",
    "--input",
    "-l",
    "--language",
    "-o",
    "--output",
    "-d",
    "--output-dir",
    "-k",
    "--api-key",
    "--key",
    "-p",
    "--provider",
    "-m",
    "--model",
    "--base-url",
    "--api-key-env",
    "--codex-home",
    "--auth-file",
    "--api-mode",
    "--chunk-size",
    "--chunk-sleep-seconds",
    "--timeout-sec",
    "--max-tokens",
    "--temperature",
    "--max-retries",
    "--retry-base-delay",
    "--suffix",
    "--translated-suffix-aliases",
}
BOOLEAN_OPTIONS = {"--flat", "--no-flat", "--force", "--no-force"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdtomd",
        description="Translate markdown files with multiple LLM providers",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_package_version()}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    translate_parser = subparsers.add_parser("translate", help="Translate markdown files")
    _add_translate_args(translate_parser)

    estimate_parser = subparsers.add_parser("estimate", help="Estimate pending translation tokens")
    _add_estimate_args(estimate_parser)

    run_parser = subparsers.add_parser("run", help=argparse.SUPPRESS)
    _add_translate_args(run_parser)

    subparsers.add_parser("languages", help="List common supported languages")
    models_parser = subparsers.add_parser("models", help="List featured models")
    _add_shared_config_arg(models_parser)
    subparsers.add_parser("providers", help="List supported LLM providers")
    subparsers.add_parser("setup", help="Show setup guide")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(_normalize_argv(argv))

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
    if args.command == "run":
        return _handle_run(args)
    return _handle_translate(args)


def _handle_run(args: argparse.Namespace) -> int:
    if _json_enabled(args):
        estimate_exit_code, estimate_payload = _execute_estimate(args)
        if estimate_exit_code != 0:
            _print_json(
                {
                    "command": "run",
                    "ok": False,
                    "input": getattr(args, "input", ""),
                    "estimate": estimate_payload,
                    "error": estimate_payload.get("error"),
                }
            )
            return estimate_exit_code

        translate_exit_code, translate_payload = _execute_translate(args)
        _print_json(
            {
                "command": "run",
                "ok": translate_exit_code == 0,
                "input": getattr(args, "input", ""),
                "estimate": estimate_payload,
                "translate": translate_payload,
                "error": None if translate_exit_code == 0 else translate_payload.get("error"),
            }
        )
        return translate_exit_code

    estimate_exit_code = _handle_estimate(args)
    if estimate_exit_code != 0:
        return estimate_exit_code

    print("开始翻译:")
    return _handle_translate(args)


def _get_package_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject_path.exists():
        for line in pyproject_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("version = "):
                return line.split("=", 1)[1].strip().strip('"')

    try:
        return importlib.metadata.version("mdtomd")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


def _handle_translate(args: argparse.Namespace) -> int:
    exit_code, payload = _execute_translate(args)
    if _json_enabled(args):
        _print_json(payload)
    else:
        _print_translate_payload(payload)
    return exit_code


def _execute_translate(args: argparse.Namespace) -> tuple[int, dict]:
    try:
        config = load_config(getattr(args, "config", None))
    except Exception as exc:
        return 1, _build_error_payload("translate", "config", str(exc), f"配置文件加载失败: {exc}")

    options = resolve_translate_options(args, config)
    if not options.language:
        return 1, _build_error_payload(
            "translate",
            "validation",
            "missing target language",
            "缺少目标语言，请用 --language 或在 config.yaml 的 defaults.language 中设置。",
            input_value=options.input,
        )

    batch_input, batch_output_dir, is_batch = _resolve_batch_input(options.input, options.output_dir)
    matched_files = glob.glob(batch_input if is_batch else options.input, recursive=True)
    is_pattern = is_batch or contains_glob(options.input) or len(matched_files) > 1

    try:
        llm_client = create_llm_client(**options.llm_kwargs())
    except Exception as exc:
        return 1, _build_error_payload(
            "translate",
            "llm",
            str(exc),
            f"LLM 配置失败: {exc}",
            input_value=options.input,
            language=options.language,
            provider=options.provider,
            model=options.model,
        )

    translator = MarkdownTranslator(llm_client, chunk_sleep_seconds=options.chunk_sleep_seconds)
    progress_callback_factory = _build_progress_callback_factory(
        json_enabled=_json_enabled(args),
        command="translate",
    )

    try:
        if is_pattern:
            results = translator.translate_files(
                batch_input,
                batch_output_dir,
                options.language,
                options=TranslateFilesOptions(
                    progress_callback=progress_callback_factory,
                    preserve_structure=not options.flat,
                    suffix=options.suffix,
                    translated_suffix_aliases=options.translated_suffix_aliases,
                    skip_existing=not options.force,
                ),
                chunk_size=options.chunk_size,
            )
            payload = _build_translate_payload(
                config=config,
                options=options,
                provider=llm_client.config.provider,
                model=llm_client.config.model,
                mode="batch",
                input_value=batch_input,
                output_dir=batch_output_dir,
                results=results,
            )
            return _translate_exit_code(payload), payload

        input_path = Path(options.input)
        if not input_path.exists():
            return 1, _build_error_payload(
                "translate",
                "validation",
                f"input file does not exist: {input_path}",
                f"输入文件不存在: {input_path}",
                input_value=options.input,
                language=options.language,
            )
        if not MarkdownTranslator.is_markdown_file(input_path):
            return 1, _build_error_payload(
                "translate",
                "validation",
                "input file must be .md / .markdown / .mdx",
                "输入文件必须是 .md / .markdown / .mdx",
                input_value=options.input,
                language=options.language,
            )

        effective_suffix = resolve_effective_suffix(options.suffix, options.language)
        output_path = resolve_single_output_path(
            input_path=input_path,
            output=options.output,
            output_dir=options.output_dir,
            suffix=options.suffix,
            language=options.language,
        )
        if not options.force and is_translated_input(
            input_path,
            effective_suffix,
            options.translated_suffix_aliases,
        ):
            payload = _build_translate_payload(
                config=config,
                options=options,
                provider=llm_client.config.provider,
                model=llm_client.config.model,
                mode="single",
                input_value=str(input_path),
                output_dir=options.output_dir,
                results=[
                    {
                        "inputPath": str(input_path),
                        "outputPath": None,
                        "success": True,
                        "skipped": True,
                        "reason": "translated-input",
                    }
                ],
            )
            return 0, payload
        if translator.is_empty_markdown_file(input_path):
            payload = _build_translate_payload(
                config=config,
                options=options,
                provider=llm_client.config.provider,
                model=llm_client.config.model,
                mode="single",
                input_value=str(input_path),
                output_dir=options.output_dir,
                results=[
                    {
                        "inputPath": str(input_path),
                        "outputPath": str(output_path),
                        "success": True,
                        "skipped": True,
                        "reason": "empty-input",
                    }
                ],
            )
            return 0, payload
        existing_output_path = resolve_existing_output_path(
            input_path,
            output_path,
            options.translated_suffix_aliases,
        )
        if not options.force and should_skip_existing(
            input_path,
            output_path,
            options.translated_suffix_aliases,
        ):
            payload = _build_translate_payload(
                config=config,
                options=options,
                provider=llm_client.config.provider,
                model=llm_client.config.model,
                mode="single",
                input_value=str(input_path),
                output_dir=options.output_dir,
                results=[
                    {
                        "inputPath": str(input_path),
                        "outputPath": str(existing_output_path or output_path),
                        "success": True,
                        "skipped": True,
                        "reason": "up-to-date",
                    }
                ],
            )
            return 0, payload

        will_overwrite = output_path.exists()
        result = translator.translate_file(
            input_path,
            output_path,
            options.language,
            progress_callback=_build_single_file_progress_callback(
                input_path=input_path,
                json_enabled=_json_enabled(args),
                command="translate",
            ),
            chunk_size=options.chunk_size,
        )
        payload = _build_translate_payload(
            config=config,
            options=options,
            provider=llm_client.config.provider,
            model=llm_client.config.model,
            mode="single",
            input_value=str(input_path),
            output_dir=options.output_dir,
            results=[result],
            warning=f"警告: 输出文件已存在，将被覆盖: {output_path}" if will_overwrite else "",
        )
        return 0, payload
    except Exception as exc:
        return 1, _build_error_payload(
            "translate",
            "translate",
            str(exc),
            f"翻译失败: {exc}",
            input_value=options.input,
            language=options.language,
            provider=llm_client.config.provider,
            model=llm_client.config.model,
        )


def _handle_estimate(args: argparse.Namespace) -> int:
    exit_code, payload = _execute_estimate(args)
    if _json_enabled(args):
        _print_json(payload)
    else:
        _print_estimate_payload(payload)
    return exit_code


def _execute_estimate(args: argparse.Namespace) -> tuple[int, dict]:
    try:
        config = load_config(getattr(args, "config", None))
    except Exception as exc:
        return 1, _build_error_payload("estimate", "config", str(exc), f"配置文件加载失败: {exc}")

    options = resolve_estimate_options(args, config)
    if not options.language:
        return 1, _build_error_payload(
            "estimate",
            "validation",
            "missing target language",
            "缺少目标语言，请用 --language 或在 config.yaml 的 defaults.language 中设置。",
            input_value=options.input,
        )

    translator = MarkdownTranslator(None, chunk_sleep_seconds=0.0)
    batch_input, batch_output_dir, is_batch = _resolve_batch_input(options.input, options.output_dir)
    matched_files = glob.glob(batch_input if is_batch else options.input, recursive=True)
    is_pattern = is_batch or contains_glob(options.input) or len(matched_files) > 1

    try:
        if is_pattern:
            estimate = translator.estimate_files_tokens(
                batch_input,
                batch_output_dir,
                options.language,
                options=TranslateFilesOptions(
                    preserve_structure=not options.flat,
                    suffix=options.suffix,
                    translated_suffix_aliases=options.translated_suffix_aliases,
                    skip_existing=not options.force,
                ),
                chunk_size=options.chunk_size,
                model=options.resolved_model,
            )
            payload = _build_estimate_payload(
                config=config,
                options=options,
                mode="batch",
                input_value=batch_input,
                output_dir=batch_output_dir,
                tokenizer=estimate.tokenizer,
                approximate=estimate.approximate,
                file_count=estimate.file_count,
                pending_file_count=estimate.pending_file_count,
                skipped_file_count=estimate.skipped_file_count,
                chunk_count=estimate.chunk_count,
                source_chars=estimate.source_chars,
                source_tokens=estimate.source_tokens,
                request_input_tokens=estimate.request_input_tokens,
                files=[_serialize_file_estimate(item) for item in estimate.files],
            )
            return 0, payload

        input_path = Path(options.input)
        if not input_path.exists():
            return 1, _build_error_payload(
                "estimate",
                "validation",
                f"input file does not exist: {input_path}",
                f"输入文件不存在: {input_path}",
                input_value=options.input,
                language=options.language,
            )
        if not MarkdownTranslator.is_markdown_file(input_path):
            return 1, _build_error_payload(
                "estimate",
                "validation",
                "input file must be .md / .markdown / .mdx",
                "输入文件必须是 .md / .markdown / .mdx",
                input_value=options.input,
                language=options.language,
            )

        effective_suffix = resolve_effective_suffix(options.suffix, options.language)
        output_path = resolve_single_output_path(
            input_path=input_path,
            output=options.output,
            output_dir=options.output_dir,
            suffix=options.suffix,
            language=options.language,
        )
        if not options.force and is_translated_input(
            input_path,
            effective_suffix,
            options.translated_suffix_aliases,
        ):
            payload = _build_estimate_payload(
                config=config,
                options=options,
                mode="single",
                input_value=str(input_path),
                output_dir=options.output_dir,
                tokenizer="heuristic",
                approximate=True,
                file_count=1,
                pending_file_count=0,
                skipped_file_count=1,
                chunk_count=0,
                source_chars=0,
                source_tokens=0,
                request_input_tokens=0,
                files=[
                    {
                        "input_path": str(input_path),
                        "output_path": None,
                        "chunk_count": 0,
                        "source_chars": 0,
                        "source_tokens": 0,
                        "request_input_tokens": 0,
                        "skipped": True,
                        "reason": "translated-input",
                    }
                ],
            )
            return 0, payload
        if translator.is_empty_markdown_file(input_path):
            payload = _build_estimate_payload(
                config=config,
                options=options,
                mode="single",
                input_value=str(input_path),
                output_dir=options.output_dir,
                tokenizer="heuristic",
                approximate=True,
                file_count=1,
                pending_file_count=0,
                skipped_file_count=1,
                chunk_count=0,
                source_chars=0,
                source_tokens=0,
                request_input_tokens=0,
                files=[
                    {
                        "input_path": str(input_path),
                        "output_path": str(output_path),
                        "chunk_count": 0,
                        "source_chars": 0,
                        "source_tokens": 0,
                        "request_input_tokens": 0,
                        "skipped": True,
                        "reason": "empty-input",
                    }
                ],
            )
            return 0, payload
        existing_output_path = resolve_existing_output_path(
            input_path,
            output_path,
            options.translated_suffix_aliases,
        )
        if not options.force and should_skip_existing(
            input_path,
            output_path,
            options.translated_suffix_aliases,
        ):
            payload = _build_estimate_payload(
                config=config,
                options=options,
                mode="single",
                input_value=str(input_path),
                output_dir=options.output_dir,
                tokenizer="heuristic",
                approximate=True,
                file_count=1,
                pending_file_count=0,
                skipped_file_count=1,
                chunk_count=0,
                source_chars=0,
                source_tokens=0,
                request_input_tokens=0,
                files=[
                    {
                        "input_path": str(input_path),
                        "output_path": str(existing_output_path or output_path),
                        "chunk_count": 0,
                        "source_chars": 0,
                        "source_tokens": 0,
                        "request_input_tokens": 0,
                        "skipped": True,
                        "reason": "up-to-date",
                    }
                ],
            )
            return 0, payload

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

        payload = _build_estimate_payload(
            config=config,
            options=options,
            mode="single",
            input_value=str(input_path),
            output_dir=options.output_dir,
            tokenizer=tokenizer_label,
            approximate=approximate,
            file_count=1,
            pending_file_count=1,
            skipped_file_count=0,
            chunk_count=estimate.chunk_count,
            source_chars=estimate.source_chars,
            source_tokens=estimate.source_tokens,
            request_input_tokens=estimate.request_input_tokens,
            files=[_serialize_file_estimate(estimate)],
        )
        return 0, payload
    except Exception as exc:
        return 1, _build_error_payload(
            "estimate",
            "estimate",
            str(exc),
            f"统计失败: {exc}",
            input_value=options.input,
            language=options.language,
            provider=options.provider,
            model=options.resolved_model,
        )


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
    print("   mdtomd providers")
    print("2. 看内置推荐模型:")
    print("   mdtomd models")
    print("3. 安装 CLI 并尽量自动放进 PATH:")
    print("   ./scripts/install_cli.sh")
    print("   powershell -ExecutionPolicy Bypass -File .\\scripts\\install_cli.ps1")
    print("4. 编辑 config.yaml，或设置环境变量，例如:")
    print('   export OPENROUTER_API_KEY="your-key"')
    print('   export OPENAI_API_KEY="your-key"')
    print('   export OPENAI_CODEX_ACCESS_TOKEN="your-token"')
    print('   export ANTHROPIC_API_KEY="your-key"')
    print('   export GEMINI_API_KEY="your-key"')
    print("5. 开始翻译:")
    print("   mdtomd translate -i README.md")
    print("6. 先做 token 统计:")
    print("   mdtomd estimate -i README.md -l Chinese")
    print("7. 如果是自建 OpenAI 兼容接口:")
    print("   mdtomd translate -i README.md --provider openai-compatible --base-url http://localhost:8000/v1 --api-key your-key --model qwen2.5-14b-instruct")
    return 0


def _add_shared_config_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-c", "--config", help="Path to config.yaml, default is ./config.yaml or ./config.yml")


def _add_shared_input_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-i", "--input", required=True, help='Input file path or glob pattern, such as "README.md" or "docs/**/*.md"')


def _add_translate_args(parser: argparse.ArgumentParser) -> None:
    _add_shared_config_arg(parser)
    _add_shared_input_arg(parser)
    parser.add_argument("-l", "--language", help="Target language")
    parser.add_argument("-o", "--output", help="Output file path for single file translation")
    parser.add_argument("-d", "--output-dir", help="Output directory for batch translation or single file translation")
    parser.add_argument("-k", "--api-key", "--key", dest="api_key", help="API key for the selected provider")
    parser.add_argument("-p", "--provider", help="Provider name, such as auto/openai/openai-codex/openrouter/anthropic/gemini/deepseek/minimax/kimi/openai-compatible")
    parser.add_argument("-m", "--model", help="Override model name")
    parser.add_argument("--base-url", help="Override API base URL, mainly for openai-compatible/custom endpoints")
    parser.add_argument("--api-key-env", help="Read API key from the specified environment variable")
    parser.add_argument("--codex-home", help="Override CODEX_HOME used by openai-codex to locate auth.json")
    parser.add_argument("--auth-file", help="Explicit auth.json path for openai-codex")
    parser.add_argument("--api-mode", choices=("auto", "chat_completions", "responses"), help="OpenAI transport mode")
    parser.add_argument("--chunk-size", type=int, help="Override markdown chunk size")
    parser.add_argument("--chunk-sleep-seconds", type=float, help="Sleep interval between chunk requests")
    parser.add_argument("--timeout-sec", type=float, help="LLM request timeout")
    parser.add_argument("--max-tokens", type=int, help="LLM max output tokens")
    parser.add_argument("--temperature", type=float, help="LLM sampling temperature")
    parser.add_argument("--max-retries", type=int, help="LLM retry count")
    parser.add_argument("--retry-base-delay", type=float, help="Base retry delay in seconds")
    parser.add_argument("--flat", action=argparse.BooleanOptionalAction, default=None, help="Use flat output structure in batch mode")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--suffix", help="Custom suffix for output files")
    parser.add_argument("--translated-suffix-aliases", help="Comma-separated translated suffix aliases treated as existing translations, such as cn,chinese")
    parser.add_argument("--force", action=argparse.BooleanOptionalAction, default=None, help="Ignore incremental skip and re-translate existing outputs")


def _add_estimate_args(parser: argparse.ArgumentParser) -> None:
    _add_shared_config_arg(parser)
    _add_shared_input_arg(parser)
    parser.add_argument("-l", "--language", help="Target language")
    parser.add_argument("-o", "--output", help="Output file path for single file estimate")
    parser.add_argument("-d", "--output-dir", help="Output directory for batch estimate or single file estimate")
    parser.add_argument("-p", "--provider", help="Provider name, used to select default model and tokenizer")
    parser.add_argument("-m", "--model", help="Override model name for token estimation")
    parser.add_argument("--chunk-size", type=int, help="Override markdown chunk size")
    parser.add_argument("--timeout-sec", type=float, help="Reserved for editor integration, accepted but not used in estimate")
    parser.add_argument("--max-tokens", type=int, help="Use this max_tokens as the default chunk size when --chunk-size is not set")
    parser.add_argument("--flat", action=argparse.BooleanOptionalAction, default=None, help="Use flat output structure in batch mode")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--suffix", help="Custom suffix for output files")
    parser.add_argument("--translated-suffix-aliases", help="Comma-separated translated suffix aliases treated as existing translations, such as cn,chinese")
    parser.add_argument("--force", action=argparse.BooleanOptionalAction, default=None, help="Ignore incremental skip and estimate all matched source files")


def _resolve_batch_input(input_value: str, output_dir: str) -> tuple[str, str, bool]:
    if is_directory_input(input_value):
        directory = str(Path(input_value).resolve())
        return resolve_directory_input_pattern(directory), output_dir or directory, True
    if contains_glob(input_value):
        base_dir = str(resolve_glob_base_dir(input_value).resolve())
        return input_value, output_dir or base_dir, True
    return input_value, output_dir, False


def _json_enabled(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False))


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _emit_progress_event(
    *,
    command: str,
    file_index: int,
    file_total: int,
    chunk_index: int,
    chunk_total: int,
    file_path: str,
) -> None:
    payload = {
        "type": "progress",
        "command": command,
        "file_index": file_index,
        "file_total": file_total,
        "chunk_index": chunk_index,
        "chunk_total": chunk_total,
        "file_path": file_path,
    }
    sys.stderr.write(f"{PROGRESS_EVENT_PREFIX}{json.dumps(payload, ensure_ascii=False)}\n")
    sys.stderr.flush()


def _build_progress_callback_factory(*, json_enabled: bool, command: str):
    if json_enabled:
        def _progress(file_num: int, total_files: int, chunk: int, total_chunks: int, file_name: str) -> None:
            _emit_progress_event(
                command=command,
                file_index=file_num,
                file_total=total_files,
                chunk_index=chunk,
                chunk_total=total_chunks,
                file_path=file_name,
            )

        return _progress

    def _human_progress(file_num: int, total_files: int, chunk: int, total_chunks: int, file_name: str) -> None:
        print(f"[{file_num}/{total_files}] {Path(file_name).name} chunk {chunk}/{total_chunks}")

    return _human_progress


def _build_single_file_progress_callback(*, input_path: Path, json_enabled: bool, command: str):
    if json_enabled:
        def _progress(chunk: int, total: int) -> None:
            _emit_progress_event(
                command=command,
                file_index=1,
                file_total=1,
                chunk_index=chunk,
                chunk_total=total,
                file_path=str(input_path),
            )

        return _progress

    return lambda chunk, total: print(f"chunk {chunk}/{total}")


def _build_error_payload(
    command: str,
    stage: str,
    message: str,
    display_message: str,
    *,
    input_value: str | None = None,
    language: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    payload = {
        "command": command,
        "ok": False,
        "error": {
            "stage": stage,
            "message": message,
            "display_message": display_message,
        },
    }
    if input_value:
        payload["input"] = input_value
    if language:
        payload["language"] = language
    if provider is not None:
        payload["provider"] = provider
    if model is not None:
        payload["model"] = model
    return payload


def _build_translate_payload(
    *,
    config,
    options,
    provider: str,
    model: str,
    mode: str,
    input_value: str,
    output_dir: str | None,
    results: list[dict],
    warning: str = "",
) -> dict:
    normalized_results = [_normalize_translate_result(item) for item in results]
    summary = _summarize_translate_results(normalized_results)
    effective_suffix = resolve_effective_suffix(options.suffix, options.language)
    payload = {
        "command": "translate",
        "ok": summary["failed"] == 0,
        "mode": mode,
        "input": options.input,
        "resolved_input": input_value,
        "output_dir": output_dir or None,
        "language": options.language,
        "suffix": effective_suffix,
        "provider": provider,
        "model": model,
        "chunk_size": options.chunk_size,
        "max_tokens": options.max_tokens,
        "config_path": str(Path(config.path).resolve()) if config.path else None,
        "summary": summary,
        "results": normalized_results,
    }
    if warning:
        payload["warning"] = warning
    return payload


def _build_estimate_payload(
    *,
    config,
    options,
    mode: str,
    input_value: str,
    output_dir: str | None,
    tokenizer: str,
    approximate: bool,
    file_count: int,
    pending_file_count: int,
    skipped_file_count: int,
    chunk_count: int,
    source_chars: int,
    source_tokens: int,
    request_input_tokens: int,
    files: list[dict],
) -> dict:
    effective_suffix = resolve_effective_suffix(options.suffix, options.language)
    return {
        "command": "estimate",
        "ok": True,
        "mode": mode,
        "input": options.input,
        "resolved_input": input_value,
        "output_dir": output_dir or None,
        "language": options.language,
        "suffix": effective_suffix,
        "provider": options.provider,
        "model": options.resolved_model,
        "chunk_size": options.chunk_size,
        "max_tokens": options.max_tokens,
        "config_path": str(Path(config.path).resolve()) if config.path else None,
        "tokenizer": tokenizer,
        "approximate": approximate,
        "summary": {
            "file_count": file_count,
            "pending_file_count": pending_file_count,
            "skipped_file_count": skipped_file_count,
            "chunk_count": chunk_count,
            "source_chars": source_chars,
            "source_tokens": source_tokens,
            "request_input_tokens": request_input_tokens,
        },
        "files": files,
        "pricing": _build_pricing_payload(
            config=config,
            provider=options.provider,
            model=options.resolved_model,
            input_tokens=request_input_tokens,
            approx_output_tokens=source_tokens,
        ),
    }


def _normalize_translate_result(item: dict) -> dict:
    result = dict(item)
    error = result.get("error")
    success = result.get("success")
    if success is None:
        success = not error
    return {
        "input_path": result.get("inputPath") or result.get("input_path"),
        "output_path": result.get("outputPath") or result.get("output_path"),
        "target_language": result.get("targetLanguage") or result.get("target_language"),
        "chunk_count": _optional_int(result.get("chunkCount") if "chunkCount" in result else result.get("chunk_count")),
        "source_tokens": _optional_int(result.get("sourceTokens") if "sourceTokens" in result else result.get("source_tokens")),
        "request_input_tokens": _optional_int(result.get("requestInputTokens") if "requestInputTokens" in result else result.get("request_input_tokens")),
        "prompt_tokens": _optional_int(result.get("promptTokens") if "promptTokens" in result else result.get("prompt_tokens")),
        "completion_tokens": _optional_int(result.get("completionTokens") if "completionTokens" in result else result.get("completion_tokens")),
        "total_tokens": _optional_int(result.get("totalTokens") if "totalTokens" in result else result.get("total_tokens")),
        "original_length": _optional_int(result.get("originalLength") if "originalLength" in result else result.get("original_length")),
        "translated_length": _optional_int(result.get("translatedLength") if "translatedLength" in result else result.get("translated_length")),
        "tokenizer": result.get("tokenizer"),
        "approximate": result.get("approximate"),
        "success": bool(success),
        "skipped": bool(result.get("skipped", False)),
        "reason": str(result.get("reason", "")),
        "error": error,
    }


def _serialize_file_estimate(item) -> dict:
    if isinstance(item, dict):
        return {
            "input_path": item.get("input_path"),
            "output_path": item.get("output_path"),
            "chunk_count": _optional_int(item.get("chunk_count")),
            "source_chars": _optional_int(item.get("source_chars")),
            "source_tokens": _optional_int(item.get("source_tokens")),
            "request_input_tokens": _optional_int(item.get("request_input_tokens")),
            "skipped": bool(item.get("skipped", False)),
            "reason": str(item.get("reason", "")),
        }
    return {
        "input_path": item.input_path,
        "output_path": item.output_path,
        "chunk_count": item.chunk_count,
        "source_chars": item.source_chars,
        "source_tokens": item.source_tokens,
        "request_input_tokens": item.request_input_tokens,
        "skipped": item.skipped,
        "reason": item.reason,
    }


def _summarize_translate_results(results: list[dict]) -> dict:
    skipped = sum(1 for item in results if item.get("skipped"))
    failed = sum(1 for item in results if item.get("error"))
    successful = sum(1 for item in results if not item.get("error") and not item.get("skipped"))
    return {
        "file_count": len(results),
        "successful": successful,
        "skipped": skipped,
        "failed": failed,
    }


def _translate_exit_code(payload: dict) -> int:
    return 0 if payload["summary"]["failed"] == 0 else 1


def _build_pricing_payload(*, config, provider: str | None, model: str | None, input_tokens: int, approx_output_tokens: int) -> dict:
    return {
        "selected_model": _build_price_item(
            provider=provider,
            model=model,
            label="",
            input_tokens=input_tokens,
            approx_output_tokens=approx_output_tokens,
        ),
        "featured_models": [
            _build_price_item(
                provider=item["provider"],
                model=item["model"],
                label=item["label"] or item["model"],
                input_tokens=input_tokens,
                approx_output_tokens=approx_output_tokens,
            )
            for item in get_featured_models(config)
        ],
    }


def _build_price_item(
    *,
    provider: str | None,
    model: str | None,
    label: str,
    input_tokens: int,
    approx_output_tokens: int,
) -> dict:
    item = {
        "provider": provider or "",
        "model": model or "",
        "label": label or (model or ""),
    }
    price = lookup_model_price(provider, model)
    if price is None:
        item["available"] = False
        return item

    cost = estimate_cost(price, input_tokens=input_tokens, approx_output_tokens=approx_output_tokens)
    item.update(
        {
            "available": True,
            "currency": price.currency,
            "input_per_million": price.input_per_million,
            "output_per_million": price.output_per_million,
            "input_cached_per_million": price.input_cached_per_million,
            "source": price.source,
            "note": price.note,
            "estimated_input_cost": cost.input_cost,
            "estimated_output_cost": cost.output_cost_if_source_tokens_match,
            "estimated_total_cost": cost.total_cost_if_source_tokens_match,
        }
    )
    return item


def _print_translate_payload(payload: dict) -> None:
    if payload.get("error"):
        print(payload["error"].get("display_message") or payload["error"]["message"])
        return

    if payload["mode"] == "batch":
        print(f"批量翻译: {payload['resolved_input']}")
        print(f"输出目录: {Path(payload['output_dir']).resolve()}")
        print(f"目标语言: {payload['language']}")
        print(f"LLM: {payload['provider']} / {payload['model']}")
        if payload.get("config_path"):
            print(f"配置文件: {payload['config_path']}")
        _print_translate_summary(payload)
        return

    result = payload["results"][0]
    if result.get("skipped"):
        if result.get("reason") == "translated-input":
            print(f"跳过已翻译输入: {result['input_path']}")
            return
        if result.get("reason") == "up-to-date":
            print(f"跳过已是最新输出: {result['output_path']}")
            return
        if result.get("reason") == "empty-input":
            print(f"跳过空文件: {result['input_path']}")
            return

    if payload.get("warning"):
        print(payload["warning"])
    print(f"输入文件: {Path(result['input_path']).resolve()}")
    print(f"输出文件: {Path(result['output_path']).resolve()}")
    print(f"目标语言: {payload['language']}")
    print(f"LLM: {payload['provider']} / {payload['model']}")
    if payload.get("config_path"):
        print(f"配置文件: {payload['config_path']}")
    if result.get("chunk_count") is not None:
        print(f"分块数: {result['chunk_count']}")
    if result.get("source_tokens") is not None:
        print(f"原文 tokens: {result['source_tokens']}")
    if result.get("request_input_tokens") is not None:
        print(f"请求输入 tokens: {result['request_input_tokens']}")
    if result.get("completion_tokens") is not None:
        print(f"回复输出 tokens: {result['completion_tokens']}")
    if result.get("original_length") is not None:
        print(f"原文长度: {result['original_length']}")
    if result.get("translated_length") is not None:
        print(f"译文长度: {result['translated_length']}")
    print(f"已写入: {result['output_path']}")


def _print_translate_summary(payload: dict) -> None:
    summary = payload["summary"]
    print(f"完成: {summary['successful']}/{summary['file_count']}")
    if summary["skipped"]:
        print(f"跳过: {summary['skipped']}")
    if summary["failed"]:
        print(f"失败: {summary['failed']}")
        for item in payload["results"]:
            if item.get("error"):
                print(f"- {item['input_path']}: {item['error']}")


def _print_estimate_payload(payload: dict) -> None:
    if payload.get("error"):
        print(payload["error"].get("display_message") or payload["error"]["message"])
        return

    summary = payload["summary"]
    if payload["mode"] == "single" and summary["pending_file_count"] == 0 and summary["skipped_file_count"] == 1:
        item = payload["files"][0]
        if item.get("reason") == "translated-input":
            print(f"跳过已翻译输入: {item['input_path']}")
            return
        if item.get("reason") == "up-to-date":
            print(f"跳过已是最新输出: {item['output_path']}")
            return
        if item.get("reason") == "empty-input":
            print(f"跳过空文件: {item['input_path']}")
            return

    if payload["mode"] == "batch":
        print("统计模式: 批量")
        print(f"输入模式: {payload['resolved_input']}")
        print(f"输出目录: {Path(payload['output_dir']).resolve()}")
    else:
        item = payload["files"][0]
        print("统计模式: 单文件")
        print(f"输入文件: {Path(item['input_path']).resolve()}")
        print(f"输出文件: {Path(item['output_path']).resolve()}")
    print(f"目标语言: {payload['language']}")
    print(f"模型: {payload['provider'] or 'auto'} / {payload['model'] or '-'}")
    print(f"tokenizer: {payload['tokenizer']}{' (近似)' if payload['approximate'] else ''}")
    if payload["mode"] == "batch":
        print(f"文件总数: {summary['file_count']}")
        print(f"待翻译文件: {summary['pending_file_count']}")
        print(f"跳过文件: {summary['skipped_file_count']}")
        print(f"分块总数: {summary['chunk_count']}")
        print(f"待翻译字符: {summary['source_chars']}")
    else:
        print(f"分块数: {summary['chunk_count']}")
        print(f"原文字符: {summary['source_chars']}")
    print(f"原文 tokens: {summary['source_tokens']}")
    print(f"请求输入 tokens: {summary['request_input_tokens']}")
    _print_selected_price(payload["pricing"]["selected_model"])
    _print_featured_prices(payload["pricing"]["featured_models"])
    if payload["mode"] == "batch":
        pending_files = [item for item in payload["files"] if not item.get("skipped")]
        if pending_files:
            print("高消耗文件:")
            for item in sorted(pending_files, key=lambda current: current.get("request_input_tokens") or 0, reverse=True)[:5]:
                print(
                    f"- {item['input_path']} "
                    f"chunks={item['chunk_count']} "
                    f"source_tokens={item['source_tokens']} "
                    f"request_tokens={item['request_input_tokens']}"
                )


def _print_selected_price(item: dict) -> None:
    if not item.get("available"):
        print("价格: 未内置该 provider/model 的单价")
        return
    print(f"价格: {item['currency']} input={item['input_per_million']}/MTokens output={item['output_per_million']}/MTokens")
    print(f"预计输入成本: {item['estimated_input_cost']:.6f} {item['currency']}")
    print(f"粗估总成本: {item['estimated_total_cost']:.6f} {item['currency']} (按输出 tokens≈原文 tokens)")
    if item.get("note"):
        print(f"价格说明: {item['note']}")
    if item.get("source"):
        print(f"价格来源: {item['source']}")


def _print_featured_prices(items: list[dict]) -> None:
    print("推荐模型费用:")
    for item in items:
        if not item.get("available"):
            print(f"- {item['label']} | {item['provider']} / {item['model']} | 未内置价格")
            continue
        print(
            f"- {item['label']} | {item['provider']} / {item['model']} | "
            f"input={item['estimated_input_cost']:.6f} {item['currency']} | "
            f"total={item['estimated_total_cost']:.6f} {item['currency']}"
        )


def _optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _normalize_argv(argv: Optional[Sequence[str]]) -> list[str]:
    normalized = list(sys.argv[1:] if argv is None else argv)
    if not normalized:
        return normalized
    if _contains_input_option(normalized):
        return ["run", *normalized] if _has_no_command(normalized) else normalized

    positional_index = _find_first_positional_index(normalized)
    if positional_index is None:
        return normalized

    token = normalized[positional_index]
    if token in COMMANDS:
        return normalized
    return ["run", *normalized[:positional_index], "-i", token, *normalized[positional_index + 1 :]]


def _has_no_command(argv: Sequence[str]) -> bool:
    positional_index = _find_first_positional_index(argv)
    if positional_index is None:
        return True
    return argv[positional_index] not in COMMANDS


def _contains_input_option(argv: Sequence[str]) -> bool:
    return any(token in {"-i", "--input"} or token.startswith("--input=") for token in argv)


def _find_first_positional_index(argv: Sequence[str]) -> int | None:
    skip_next = False
    for index, token in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            return index + 1 if index + 1 < len(argv) else None
        if token.startswith("--"):
            option_name = token.split("=", 1)[0]
            if option_name in OPTIONS_WITH_VALUE and "=" not in token:
                skip_next = True
                continue
            if option_name in BOOLEAN_OPTIONS or "=" in token:
                continue
            continue
        if token.startswith("-") and token != "-":
            if token in OPTIONS_WITH_VALUE:
                skip_next = True
                continue
            continue
        return index
    return None
