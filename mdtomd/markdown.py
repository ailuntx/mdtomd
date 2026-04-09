from __future__ import annotations

import os
from pathlib import Path
from typing import Union


PathLike = Union[str, os.PathLike]


SUPPORTED_MARKDOWN_EXTENSIONS = frozenset({".md", ".markdown", ".mdx"})

SUPPORTED_LANGUAGES = (
    "Spanish",
    "French",
    "German",
    "Italian",
    "Portuguese",
    "Dutch",
    "Russian",
    "Chinese",
    "Japanese",
    "Korean",
    "Arabic",
    "Hindi",
    "Turkish",
    "Polish",
    "Swedish",
    "Norwegian",
    "Danish",
    "Finnish",
    "Greek",
    "Hebrew",
    "Thai",
    "Vietnamese",
    "Indonesian",
    "Malay",
    "Ukrainian",
    "Czech",
    "Hungarian",
    "Romanian",
    "Bulgarian",
    "Croatian",
    "Serbian",
    "Slovak",
    "Slovenian",
    "Estonian",
    "Latvian",
    "Lithuanian",
    "Catalan",
    "Basque",
    "Welsh",
    "Irish",
)


def is_markdown_file(file_path: PathLike) -> bool:
    return Path(file_path).suffix.lower() in SUPPORTED_MARKDOWN_EXTENSIONS


def language_to_suffix(target_language: str) -> str:
    return "_".join(target_language.strip().lower().split())
