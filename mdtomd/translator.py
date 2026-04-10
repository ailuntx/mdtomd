from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .llm import LLMClient, LLMResponse
from .markdown import PathLike, SUPPORTED_LANGUAGES, is_markdown_file, language_to_suffix
from .paths import build_batch_output_path, collect_markdown_files, resolve_effective_suffix, resolve_glob_base_dir, should_skip_existing
from .token_count import TokenCounter


SingleProgressCallback = Callable[[int, int], None]
BatchProgressCallback = Callable[[int, int, int, int, str], None]


@dataclass
class TranslateFilesOptions:
    progress_callback: BatchProgressCallback | None = None
    preserve_structure: bool = True
    suffix: str = ""
    skip_existing: bool = True
    skip_translated_inputs: bool = True


@dataclass(frozen=True)
class MarkdownTokenEstimate:
    chunk_count: int
    source_chars: int
    source_tokens: int
    request_input_tokens: int
    tokenizer: str
    approximate: bool


@dataclass(frozen=True)
class FileTokenEstimate:
    input_path: str
    output_path: str
    chunk_count: int = 0
    source_chars: int = 0
    source_tokens: int = 0
    request_input_tokens: int = 0
    skipped: bool = False
    reason: str = ""


@dataclass(frozen=True)
class BatchTokenEstimate:
    file_count: int
    pending_file_count: int
    skipped_file_count: int
    chunk_count: int
    source_chars: int
    source_tokens: int
    request_input_tokens: int
    tokenizer: str
    approximate: bool
    files: list[FileTokenEstimate]


@dataclass(frozen=True)
class MarkdownTranslationResult:
    content: str
    chunk_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class MarkdownTranslator:
    DEFAULT_CHUNK_SIZE = 12000
    SUPPORTED_LANGUAGES = list(SUPPORTED_LANGUAGES)
    _LEADING_THINK_BLOCK_RE = re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)

    def __init__(self, llm_client: LLMClient | None, chunk_sleep_seconds: float = 0.5) -> None:
        self.llm_client = llm_client
        self.chunk_sleep_seconds = chunk_sleep_seconds

    @classmethod
    def get_supported_languages(cls) -> list[str]:
        return list(cls.SUPPORTED_LANGUAGES)

    @classmethod
    def is_markdown_file(cls, file_path: PathLike) -> bool:
        return is_markdown_file(file_path)

    @staticmethod
    def language_to_suffix(target_language: str) -> str:
        return language_to_suffix(target_language)

    def split_into_chunks(self, content: str, max_chunk_size: int | None = None, model: str = "") -> list[str]:
        chunk_size = max_chunk_size or self.DEFAULT_CHUNK_SIZE
        if chunk_size <= 0:
            raise ValueError("max_chunk_size must be greater than 0")

        token_counter = TokenCounter.for_model(model or self._resolve_chunking_model())
        newline_tokens = token_counter.count_text("\n")
        chunks: list[str] = []
        current_chunk = ""
        current_tokens = 0

        for line in content.split("\n"):
            line_tokens = token_counter.count_text(line)
            projected_tokens = current_tokens + newline_tokens + line_tokens if current_chunk else line_tokens
            if projected_tokens > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = line
                current_tokens = line_tokens
            else:
                current_chunk = f"{current_chunk}\n{line}" if current_chunk else line
                current_tokens = projected_tokens

        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        return chunks

    @staticmethod
    def create_translation_messages(text: str, target_language: str) -> tuple[str, str]:
        system = (
            "You are a professional markdown translator.\n"
            "Preserve the original markdown structure exactly.\n"
            "Do not add explanations, notes, or markdown fences.\n"
            "Do not translate URLs, file paths, or raw code.\n"
            "Translate comments inside code blocks when they are natural language.\n"
            "Keep technical terms or proper nouns in English when translation would be harmful."
        )
        user = (
            f"Translate the following markdown content from English to {target_language}.\n\n"
            "Return only the translated markdown.\n\n"
            "Markdown content:\n\n"
            f"{text}"
        )
        return system, user

    def translate_chunk(self, chunk: str, target_language: str) -> str:
        translated, _ = self._translate_chunk_with_response(chunk, target_language)
        return translated

    def _translate_chunk_with_response(self, chunk: str, target_language: str) -> tuple[str, LLMResponse]:
        if self.llm_client is None:
            raise RuntimeError("LLM client is not configured")
        system, user = self.create_translation_messages(chunk, target_language)
        response = self.llm_client.chat([{"role": "user", "content": user}], system=system)
        translated = self.clean_model_output(response.content)
        if not translated:
            raise RuntimeError("LLM returned empty translation")
        return translated, response

    @classmethod
    def clean_model_output(cls, content: str) -> str:
        cleaned = str(content or "")
        cleaned = cls._LEADING_THINK_BLOCK_RE.sub("", cleaned)
        return cleaned.strip()

    def translate_markdown(
        self,
        content: str,
        target_language: str,
        progress_callback: SingleProgressCallback | None = None,
        chunk_size: int | None = None,
    ) -> str:
        return self.translate_markdown_with_stats(
            content,
            target_language,
            progress_callback=progress_callback,
            chunk_size=chunk_size,
        ).content

    def translate_markdown_with_stats(
        self,
        content: str,
        target_language: str,
        progress_callback: SingleProgressCallback | None = None,
        chunk_size: int | None = None,
    ) -> MarkdownTranslationResult:
        chunks = self.split_into_chunks(content, max_chunk_size=chunk_size, model=self._resolve_chunking_model())
        if not chunks:
            raise ValueError("Markdown content is empty")

        translated_chunks: list[str] = []
        total_chunks = len(chunks)
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        for index, chunk in enumerate(chunks, start=1):
            if progress_callback:
                progress_callback(index, total_chunks)
            translated_chunk, response = self._translate_chunk_with_response(chunk, target_language)
            translated_chunks.append(translated_chunk)
            prompt_tokens += max(0, int(response.prompt_tokens or 0))
            completion_tokens += max(0, int(response.completion_tokens or 0))
            total_tokens += max(0, int(response.total_tokens or 0))
            if index < total_chunks and self.chunk_sleep_seconds > 0:
                time.sleep(self.chunk_sleep_seconds)

        translated_content = "\n\n".join(translated_chunks)
        if not translated_content.endswith("\n"):
            translated_content = f"{translated_content}\n"
        if total_tokens <= 0:
            total_tokens = prompt_tokens + completion_tokens
        return MarkdownTranslationResult(
            content=translated_content,
            chunk_count=total_chunks,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def estimate_markdown_tokens(
        self,
        content: str,
        target_language: str,
        chunk_size: int | None = None,
        model: str = "",
    ) -> MarkdownTokenEstimate:
        chunks = self.split_into_chunks(content, max_chunk_size=chunk_size, model=model)
        if not chunks:
            raise ValueError("Markdown content is empty")

        token_counter = TokenCounter.for_model(model)
        source_tokens = 0
        request_input_tokens = 0

        for chunk in chunks:
            source_tokens += token_counter.count_text(chunk)
            system, user = self.create_translation_messages(chunk, target_language)
            request_input_tokens += token_counter.count_messages(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]
            )

        return MarkdownTokenEstimate(
            chunk_count=len(chunks),
            source_chars=len(content),
            source_tokens=source_tokens,
            request_input_tokens=request_input_tokens,
            tokenizer=token_counter.encoding_name,
            approximate=token_counter.approximate,
        )

    def translate_file(
        self,
        input_path: PathLike,
        output_path: PathLike,
        target_language: str,
        progress_callback: SingleProgressCallback | None = None,
        chunk_size: int | None = None,
    ) -> dict:
        source_path = Path(input_path)
        destination_path = Path(output_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {source_path}")

        content = source_path.read_text(encoding="utf-8")
        if not content.strip():
            raise ValueError("Input file is empty")

        token_estimate = self.estimate_markdown_tokens(
            content,
            target_language,
            chunk_size=chunk_size,
            model=self._resolve_chunking_model(),
        )
        translation = self.translate_markdown_with_stats(
            content,
            target_language,
            progress_callback=progress_callback,
            chunk_size=chunk_size,
        )
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(translation.content, encoding="utf-8")
        return {
            "inputPath": str(source_path),
            "outputPath": str(destination_path),
            "targetLanguage": target_language,
            "originalLength": len(content),
            "translatedLength": len(translation.content),
            "chunkCount": translation.chunk_count,
            "sourceTokens": token_estimate.source_tokens,
            "requestInputTokens": token_estimate.request_input_tokens,
            "promptTokens": translation.prompt_tokens,
            "completionTokens": translation.completion_tokens,
            "totalTokens": translation.total_tokens,
            "tokenizer": token_estimate.tokenizer,
            "approximate": token_estimate.approximate,
        }

    def translate_files(
        self,
        input_pattern: str,
        output_dir: PathLike,
        target_language: str,
        options: TranslateFilesOptions | None = None,
        chunk_size: int | None = None,
    ) -> list[dict]:
        translate_options = options or TranslateFilesOptions()
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)

        effective_suffix = resolve_effective_suffix(translate_options.suffix, target_language)
        markdown_files = collect_markdown_files(
            input_pattern=input_pattern,
            suffix=effective_suffix,
            skip_translated_inputs=translate_options.skip_translated_inputs,
        )
        base_dir = resolve_glob_base_dir(input_pattern)
        results: list[dict] = []
        total_files = len(markdown_files)

        for file_index, input_file in enumerate(markdown_files, start=1):
            output_path = build_batch_output_path(
                input_file=input_file,
                output_root=output_root,
                base_dir=base_dir,
                preserve_structure=translate_options.preserve_structure,
                suffix=effective_suffix,
            )

            if translate_options.skip_existing and should_skip_existing(input_file, output_path):
                results.append(
                    {
                        "inputPath": str(input_file),
                        "outputPath": str(output_path),
                        "success": True,
                        "skipped": True,
                        "reason": "up-to-date",
                    }
                )
                continue

            try:
                progress_callback = None
                if translate_options.progress_callback:
                    progress_callback = self._wrap_batch_progress(
                        translate_options.progress_callback,
                        current_index=file_index,
                        total_files=total_files,
                        input_file=input_file,
                    )
                results.append(
                    self.translate_file(
                        input_file,
                        output_path,
                        target_language,
                        progress_callback=progress_callback,
                        chunk_size=chunk_size,
                    )
                )
            except Exception as exc:
                results.append(
                    {
                        "inputPath": str(input_file),
                        "error": str(exc),
                        "success": False,
                    }
                )

        return results

    def estimate_file_tokens(
        self,
        input_path: PathLike,
        output_path: PathLike,
        target_language: str,
        chunk_size: int | None = None,
        model: str = "",
    ) -> FileTokenEstimate:
        source_path = Path(input_path)
        destination_path = Path(output_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {source_path}")

        content = source_path.read_text(encoding="utf-8")
        if not content.strip():
            raise ValueError("Input file is empty")

        estimate = self.estimate_markdown_tokens(content, target_language, chunk_size=chunk_size, model=model)
        return FileTokenEstimate(
            input_path=str(source_path),
            output_path=str(destination_path),
            chunk_count=estimate.chunk_count,
            source_chars=estimate.source_chars,
            source_tokens=estimate.source_tokens,
            request_input_tokens=estimate.request_input_tokens,
        )

    def estimate_files_tokens(
        self,
        input_pattern: str,
        output_dir: PathLike,
        target_language: str,
        options: TranslateFilesOptions | None = None,
        chunk_size: int | None = None,
        model: str = "",
    ) -> BatchTokenEstimate:
        translate_options = options or TranslateFilesOptions()
        output_root = Path(output_dir)

        effective_suffix = resolve_effective_suffix(translate_options.suffix, target_language)
        markdown_files = collect_markdown_files(
            input_pattern=input_pattern,
            suffix=effective_suffix,
            skip_translated_inputs=translate_options.skip_translated_inputs,
        )
        token_counter = TokenCounter.for_model(model)
        base_dir = resolve_glob_base_dir(input_pattern)
        estimates: list[FileTokenEstimate] = []

        for input_file in markdown_files:
            output_path = build_batch_output_path(
                input_file=input_file,
                output_root=output_root,
                base_dir=base_dir,
                preserve_structure=translate_options.preserve_structure,
                suffix=effective_suffix,
            )
            if translate_options.skip_existing and should_skip_existing(input_file, output_path):
                estimates.append(
                    FileTokenEstimate(
                        input_path=str(input_file),
                        output_path=str(output_path),
                        skipped=True,
                        reason="up-to-date",
                    )
                )
                continue

            content = input_file.read_text(encoding="utf-8")
            if not content.strip():
                raise ValueError(f"Input file is empty: {input_file}")

            markdown_estimate = self.estimate_markdown_tokens(
                content,
                target_language,
                chunk_size=chunk_size,
                model=model,
            )
            estimates.append(
                FileTokenEstimate(
                    input_path=str(input_file),
                    output_path=str(output_path),
                    chunk_count=markdown_estimate.chunk_count,
                    source_chars=markdown_estimate.source_chars,
                    source_tokens=markdown_estimate.source_tokens,
                    request_input_tokens=markdown_estimate.request_input_tokens,
                )
            )

        pending_files = [item for item in estimates if not item.skipped]
        skipped_files = [item for item in estimates if item.skipped]
        return BatchTokenEstimate(
            file_count=len(estimates),
            pending_file_count=len(pending_files),
            skipped_file_count=len(skipped_files),
            chunk_count=sum(item.chunk_count for item in pending_files),
            source_chars=sum(item.source_chars for item in pending_files),
            source_tokens=sum(item.source_tokens for item in pending_files),
            request_input_tokens=sum(item.request_input_tokens for item in pending_files),
            tokenizer=token_counter.encoding_name,
            approximate=token_counter.approximate,
            files=estimates,
        )

    def _resolve_chunking_model(self) -> str:
        if self.llm_client is None:
            return ""
        config = getattr(self.llm_client, "config", None)
        return str(getattr(config, "model", "") or "")

    @staticmethod
    def _wrap_batch_progress(
        callback: BatchProgressCallback,
        *,
        current_index: int,
        total_files: int,
        input_file: Path,
    ) -> SingleProgressCallback:
        def _wrapped(chunk: int, total_chunks: int) -> None:
            callback(current_index, total_files, chunk, total_chunks, str(input_file))

        return _wrapped
