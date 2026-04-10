from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TokenCounter:
    model: str = ""
    encoding_name: str = "heuristic"
    approximate: bool = True
    _encoding: Any = None

    @classmethod
    def for_model(cls, model: str = "") -> "TokenCounter":
        try:
            import tiktoken
        except ImportError:
            return cls(model=model)

        encoding = None
        if model:
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                encoding = None

        if encoding is None:
            for encoding_name in ("o200k_base", "cl100k_base", "p50k_base"):
                try:
                    encoding = tiktoken.get_encoding(encoding_name)
                    break
                except KeyError:
                    continue

        if encoding is None:
            return cls(model=model)

        return cls(
            model=model,
            encoding_name=getattr(encoding, "name", "unknown"),
            approximate=False,
            _encoding=encoding,
        )

    def count_text(self, text: str) -> int:
        normalized = str(text or "")
        if not normalized:
            return 0
        if self._encoding is not None:
            try:
                return len(self._encoding.encode(normalized, disallowed_special=()))
            except TypeError:
                return len(self._encoding.encode(normalized))
        return max(1, math.ceil(len(normalized) / 4))

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        if not messages:
            return 0
        total = 0
        for message in messages:
            total += 4
            total += self.count_text(str(message.get("role", "user") or "user"))
            total += self.count_text(str(message.get("content", "") or ""))
        return total + 2
