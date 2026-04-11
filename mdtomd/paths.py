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


def normalize_suffix(value: str) -> str:
    return str(value or "").strip().strip("_").lower()


def resolve_translated_suffixes(suffix: str, translated_suffix_aliases: tuple[str, ...] = ()) -> tuple[str, ...]:
    candidates: list[str] = []
    seen: set[str] = set()
    for item in (suffix, *translated_suffix_aliases):
        normalized = normalize_suffix(item)
        if normalized and normalized not in seen:
            candidates.append(normalized)
            seen.add(normalized)
    return tuple(candidates)


def _find_existing_sibling(path: Path) -> Path | None:
    if path.parent.exists():
        target_name = path.name.lower()
        for candidate in path.parent.iterdir():
            if candidate.name.lower() == target_name:
                return candidate
    return None


def resolve_single_output_path(
    *,
    input_path: Path,
    output: str | None,
    output_dir: str | None,
    suffix: str,
    language: str,
) -> Path:
    effective_suffix = resolve_effective_suffix(suffix, language)
    if output:
        return Path(output)

    if output_dir:
        return Path(output_dir) / build_output_name(input_path, effective_suffix)

    return input_path.with_name(build_output_name(input_path, effective_suffix))


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


def is_translated_input(input_file: Path, suffix: str, translated_suffix_aliases: tuple[str, ...] = ()) -> bool:
    stem = input_file.stem.lower()
    return any(stem.endswith(f"_{item}") for item in resolve_translated_suffixes(suffix, translated_suffix_aliases))


def resolve_existing_output_path(
    input_file: Path,
    output_file: Path,
    translated_suffix_aliases: tuple[str, ...] = (),
) -> Path | None:
    matched_output = _find_existing_sibling(output_file)
    if matched_output is not None:
        return matched_output
    if output_file.exists():
        return output_file

    for alias in resolve_translated_suffixes("", translated_suffix_aliases):
        candidate = output_file.with_name(build_output_name(input_file, alias))
        matched_candidate = _find_existing_sibling(candidate)
        if matched_candidate is not None:
            return matched_candidate
        if candidate.exists():
            return candidate
    return None


def should_skip_existing(
    input_file: Path,
    output_file: Path,
    translated_suffix_aliases: tuple[str, ...] = (),
) -> bool:
    existing_output = resolve_existing_output_path(input_file, output_file, translated_suffix_aliases)
    if existing_output is None:
        return False
    return existing_output.stat().st_mtime >= input_file.stat().st_mtime


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
    translated_suffix_aliases: tuple[str, ...] = (),
) -> list[Path]:
    files = sorted(set(glob.glob(input_pattern, recursive=True)))
    if not files:
        raise FileNotFoundError(f"No files found matching pattern: {input_pattern}")

    markdown_files = [Path(file_path) for file_path in files if Path(file_path).is_file() and is_markdown_file(file_path)]
    if not markdown_files:
        raise ValueError("No markdown files found in the matched files")

    if skip_translated_inputs:
        markdown_files = [
            file_path
            for file_path in markdown_files
            if not is_translated_input(file_path, suffix, translated_suffix_aliases)
        ]
    if not markdown_files:
        raise ValueError("No source markdown files left after filtering translated files")
    return markdown_files
