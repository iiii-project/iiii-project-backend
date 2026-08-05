"""Traditional Chinese output safeguards for LLM responses."""

import re

from opencc import OpenCC

_CONVERTER = OpenCC("s2twp")
_PROTECTED_TEXT = re.compile(
    r"```[\s\S]*?```|`[^`\n]*`|https?://[^\s<>()`]+",
    re.IGNORECASE,
)


def to_traditional_chinese(text: str) -> str:
    """Convert prose while preserving Markdown code and URLs verbatim."""
    converted_parts: list[str] = []
    position = 0

    for match in _PROTECTED_TEXT.finditer(text):
        converted_parts.append(_CONVERTER.convert(text[position : match.start()]))
        converted_parts.append(match.group())
        position = match.end()

    converted_parts.append(_CONVERTER.convert(text[position:]))
    return "".join(converted_parts)
