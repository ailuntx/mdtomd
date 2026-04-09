from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _YamlLine:
    indent: int
    content: str
    line_no: int


def load_simple_yaml(text: str) -> dict[str, Any]:
    lines = _prepare_yaml_lines(text)
    if not lines:
        return {}
    value, index = _parse_yaml_block(lines, 0, lines[0].indent)
    if index != len(lines):
        raise ValueError("Unexpected trailing content in config.yaml")
    if not isinstance(value, dict):
        raise ValueError("Config root must be a mapping")
    return value


def _prepare_yaml_lines(text: str) -> list[_YamlLine]:
    prepared: list[_YamlLine] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = _strip_inline_comment(raw_line).rstrip()
        if not stripped.strip():
            continue
        if "\t" in raw_line:
            raise ValueError(f"Tabs are not supported in config.yaml (line {line_no})")
        indent = len(stripped) - len(stripped.lstrip(" "))
        prepared.append(
            _YamlLine(
                indent=indent,
                content=stripped.strip(),
                line_no=line_no,
            )
        )
    return prepared


def _strip_inline_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or line[index - 1].isspace():
                return line[:index]
    return line


def _parse_yaml_block(lines: list[_YamlLine], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    if lines[index].content.startswith("- "):
        return _parse_yaml_sequence(lines, index, indent)
    return _parse_yaml_mapping(lines, index, indent)


def _parse_yaml_mapping(lines: list[_YamlLine], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ValueError(f"Invalid indentation at line {line.line_no}")
        if line.content.startswith("- "):
            break

        key, raw_value = _split_key_value(line.content, line.line_no)
        index += 1
        if raw_value == "":
            if index < len(lines) and lines[index].indent > indent:
                value, index = _parse_yaml_block(lines, index, lines[index].indent)
            else:
                value = {}
        else:
            value = _parse_scalar(raw_value)
        result[key] = value
    return result, index


def _parse_yaml_sequence(lines: list[_YamlLine], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            raise ValueError(f"Invalid indentation at line {line.line_no}")
        if not line.content.startswith("- "):
            break

        item_text = line.content[2:].strip()
        index += 1
        if item_text == "":
            if index < len(lines) and lines[index].indent > indent:
                value, index = _parse_yaml_block(lines, index, lines[index].indent)
            else:
                value = None
            result.append(value)
            continue

        if ":" in item_text and not item_text.startswith(("http://", "https://")):
            key, raw_value = _split_key_value(item_text, line.line_no)
            if raw_value == "":
                if index < len(lines) and lines[index].indent > indent:
                    value, index = _parse_yaml_block(lines, index, lines[index].indent)
                else:
                    value = {}
            else:
                value = _parse_scalar(raw_value)
            result.append({key: value})
            continue

        result.append(_parse_scalar(item_text))
    return result, index


def _split_key_value(content: str, line_no: int) -> tuple[str, str]:
    if ":" not in content:
        raise ValueError(f"Expected key: value at line {line_no}")
    key, raw_value = content.split(":", 1)
    normalized_key = key.strip()
    if not normalized_key:
        raise ValueError(f"Empty key at line {line_no}")
    return normalized_key, raw_value.strip()


def _parse_scalar(value: str) -> Any:
    normalized = value.strip()
    if not normalized:
        return ""
    if normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        return normalized[1:-1]

    lowered = normalized.lower()
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if lowered in {"null", "none", "~"}:
        return None

    try:
        if normalized.startswith("0") and normalized not in {"0", "0.0"} and not normalized.startswith("0."):
            raise ValueError
        return int(normalized)
    except ValueError:
        pass

    try:
        return float(normalized)
    except ValueError:
        return normalized

