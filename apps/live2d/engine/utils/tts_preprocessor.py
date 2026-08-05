import re
import unicodedata

from loguru import logger


def tts_filter(
    text: str,
    remove_special_char: bool,
    ignore_brackets: bool,
    ignore_parentheses: bool,
    ignore_asterisks: bool,
    ignore_angle_brackets: bool,
) -> str:
    """Filter text before it's sent to TTS. Does not affect subtitles or LLM memory."""
    if ignore_asterisks:
        try:
            text = filter_asterisks(text)
        except Exception as e:
            logger.warning(f"Error ignoring asterisks: {e}")

    if ignore_brackets:
        try:
            text = filter_brackets(text)
        except Exception as e:
            logger.warning(f"Error ignoring brackets: {e}")

    if ignore_parentheses:
        try:
            text = filter_parentheses(text)
        except Exception as e:
            logger.warning(f"Error ignoring parentheses: {e}")

    if ignore_angle_brackets:
        try:
            text = filter_angle_brackets(text)
        except Exception as e:
            logger.warning(f"Error ignoring angle brackets: {e}")

    if remove_special_char:
        try:
            text = remove_special_characters(text)
        except Exception as e:
            logger.warning(f"Error removing special characters: {e}")

    logger.debug(f"Filtered text: {text}")
    return text


def remove_special_characters(text: str) -> str:
    normalized_text = unicodedata.normalize("NFKC", text)

    def is_valid_char(char: str) -> bool:
        category = unicodedata.category(char)
        return category.startswith("L") or category.startswith("N") or category.startswith("P") or char.isspace()

    return "".join(char for char in normalized_text if is_valid_char(char))


def _filter_nested(text: str, left: str, right: str) -> str:
    if not isinstance(text, str):
        raise TypeError("Input must be a string")
    if not text:
        return text

    result = []
    depth = 0
    for char in text:
        if char == left:
            depth += 1
        elif char == right:
            if depth > 0:
                depth -= 1
        else:
            if depth == 0:
                result.append(char)
    filtered_text = "".join(result)
    return re.sub(r"\s+", " ", filtered_text).strip()


def filter_brackets(text: str) -> str:
    return _filter_nested(text, "[", "]")


def filter_parentheses(text: str) -> str:
    return _filter_nested(text, "(", ")")


def filter_angle_brackets(text: str) -> str:
    return _filter_nested(text, "<", ">")


def filter_asterisks(text: str) -> str:
    filtered_text = re.sub(r"\*{1,}((?!\*).)*?\*{1,}", "", text)
    return re.sub(r"\s+", " ", filtered_text).strip()
