from __future__ import annotations

import glob
import os
from pathlib import Path

from .markdown import is_markdown_file, language_to_suffix


def contains_glob(value: str) -> bool:
    return any(char in value for char in "*?[")


def is_directory_input(value: str) -> bool:
    return Path(value).is_dir()


def resolve_directory_input_pattern(value: str) -> str:
    return str(Path(value) / "**/*")


def build_output_name(input_path: Path, suffix: str) -> str:
    if not suffix:
        return input_path.name
    return f"{input_path.stem}_{suffix}{input_path.suffix}"


def resolve_effective_suffix(suffix: str, language: str) -> str:
    return suffix or language_to_suffix(language)


def resolve_single_output_path(
    *,
    input_path: Path,
    output: str | None,
    output_dir: str | None,
    suffix: str,
    language: str,
) -> Path:
    if output:
        return Path(output)

    if output_dir:
        return Path(output_dir) / build_output_name(input_path, suffix)

    return input_path.with_name(build_output_name(input_path, resolve_effective_suffix(suffix, language)))


def resolve_glob_base_dir(pattern: str) -> Path:
    wildcard_positions = [index for char in "*?[" if (index := pattern.find(char)) != -1]
    if not wildcard_positions:
        parent = Path(pattern).parent
        return parent if str(parent) else Path(".")

    first_wildcard = min(wildcard_positions)
    prefix = pattern[:first_wildcard]
    last_separator = max(prefix.rfind("/"), prefix.rfind("\\"))
    if last_separator == -1:
        return Path(".")

    base_dir = prefix[:last_separator]
    if not base_dir:
        return Path("/")
    return Path(base_dir)


def is_translated_input(input_file: Path, suffix: str) -> bool:
    normalized_suffix = suffix.strip("_")
    if not normalized_suffix:
        return False
    return input_file.stem.endswith(f"_{normalized_suffix}")


def should_skip_existing(input_file: Path, output_file: Path) -> bool:
    if not output_file.exists():
        return False
    return output_file.stat().st_mtime >= input_file.stat().st_mtime


def build_batch_output_path(
    *,
    input_file: Path,
    output_root: Path,
    base_dir: Path,
    preserve_structure: bool,
    suffix: str,
) -> Path:
    output_name = build_output_name(input_file, suffix)
    if not preserve_structure:
        return output_root / output_name

    input_absolute = input_file.resolve()
    base_absolute = base_dir.resolve()
    try:
        relative_path = input_absolute.relative_to(base_absolute)
    except ValueError:
        relative_path = Path(os.path.relpath(str(input_absolute), str(base_absolute)))
    return output_root / relative_path.parent / output_name


def collect_markdown_files(
    *,
    input_pattern: str,
    suffix: str,
    skip_translated_inputs: bool,
) -> list[Path]:
    files = sorted(set(glob.glob(input_pattern, recursive=True)))
    if not files:
        raise FileNotFoundError(f"No files found matching pattern: {input_pattern}")

    markdown_files = [Path(file_path) for file_path in files if Path(file_path).is_file() and is_markdown_file(file_path)]
    if not markdown_files:
        raise ValueError("No markdown files found in the matched files")

    if skip_translated_inputs:
        markdown_files = [file_path for file_path in markdown_files if not is_translated_input(file_path, suffix)]
    if not markdown_files:
        raise ValueError("No source markdown files left after filtering translated files")
    return markdown_files
