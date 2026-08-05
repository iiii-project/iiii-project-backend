"""JSON-file-backed conversation history, one file per (conf_uid, history_uid).

Ported from upstream open_llm_vtuber's chat_history_manager.py. Trimmed to the
functions actually used by the single-conversation flow (no modify_latest_message /
rename_history_file). Rooted under paths.CHAT_HISTORY_DIR instead of a bare relative
"chat_history" path, so it no longer depends on the process's current working directory.

These are synchronous, blocking file I/O — call sites in async code must wrap calls
with `await asyncio.to_thread(...)`.
"""

import json
import os
import re
import uuid
from datetime import datetime
from typing import List, Literal, Optional, TypedDict

from loguru import logger

from .paths import CHAT_HISTORY_DIR

_SAFE_NAME_RE = re.compile("^[\\w\\-_\u0020-\u007E\u00A0-\uFFFF]+$")


class HistoryMessage(TypedDict):
    role: Literal["human", "ai"]
    timestamp: str
    content: str
    name: Optional[str]
    avatar: Optional[str]


def _sanitize_path_component(component: str) -> str:
    sanitized = os.path.basename(component.strip())
    if not sanitized or len(sanitized) > 255 or not _SAFE_NAME_RE.match(sanitized):
        raise ValueError(f"Invalid characters in path component: {component}")
    return sanitized


def _ensure_conf_dir(conf_uid: str) -> str:
    if not conf_uid:
        raise ValueError("conf_uid cannot be empty")
    base_dir = os.path.join(CHAT_HISTORY_DIR, _sanitize_path_component(conf_uid))
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def _get_safe_history_path(conf_uid: str, history_uid: str) -> str:
    base_dir = os.path.join(CHAT_HISTORY_DIR, _sanitize_path_component(conf_uid))
    full_path = os.path.normpath(os.path.join(base_dir, f"{_sanitize_path_component(history_uid)}.json"))
    if not full_path.startswith(base_dir):
        raise ValueError("Invalid path: Path traversal detected")
    return full_path


def create_new_history(conf_uid: str) -> str:
    if not conf_uid:
        logger.warning("No conf_uid provided")
        return ""

    history_uid = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{uuid.uuid4().hex}"
    conf_dir = _ensure_conf_dir(conf_uid)

    try:
        filepath = os.path.join(conf_dir, f"{history_uid}.json")
        initial_data = [{"role": "metadata", "timestamp": datetime.now().isoformat(timespec="seconds")}]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to create new history file: {e}")
        return ""

    return history_uid


def store_message(
    conf_uid: str,
    history_uid: str,
    role: Literal["human", "ai"],
    content: str,
    name: str | None = None,
    avatar: str | None = None,
):
    if not conf_uid or not history_uid:
        logger.warning("Missing conf_uid or history_uid")
        return

    filepath = _get_safe_history_path(conf_uid, history_uid)
    history_data = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except Exception:
            logger.error(f"Failed to load history file: {filepath}")

    new_item = {"role": role, "timestamp": datetime.now().isoformat(timespec="seconds"), "content": content}
    if name is not None:
        new_item["name"] = name
    if avatar is not None:
        new_item["avatar"] = avatar
    history_data.append(new_item)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)


def get_history(conf_uid: str, history_uid: str) -> List[HistoryMessage]:
    if not conf_uid or not history_uid:
        return []

    filepath = _get_safe_history_path(conf_uid, history_uid)
    if not os.path.exists(filepath):
        logger.warning(f"History file not found: {filepath}")
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            history_data = json.load(f)
        return [msg for msg in history_data if msg["role"] != "metadata"]
    except Exception:
        return []


def delete_history(conf_uid: str, history_uid: str) -> bool:
    if not conf_uid or not history_uid:
        return False

    filepath = _get_safe_history_path(conf_uid, history_uid)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
    except Exception as e:
        logger.error(f"Failed to delete history file: {e}")
    return False


def get_history_list(conf_uid: str) -> List[dict]:
    if not conf_uid:
        return []

    histories = []
    conf_dir = _ensure_conf_dir(conf_uid)
    empty_history_uids = []

    try:
        for filename in os.listdir(conf_dir):
            if not filename.endswith(".json"):
                continue
            history_uid = filename[:-5]
            filepath = os.path.join(conf_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    messages = json.load(f)
                actual_messages = [msg for msg in messages if msg["role"] != "metadata"]
                if not actual_messages:
                    empty_history_uids.append(history_uid)
                    continue
                latest_message = actual_messages[-1]
                histories.append(
                    {
                        "uid": history_uid,
                        "latest_message": latest_message,
                        "timestamp": latest_message["timestamp"] if latest_message else None,
                    }
                )
            except Exception as e:
                logger.error(f"Error reading history file {filename}: {e}")

        if empty_history_uids and len(os.listdir(conf_dir)) > 1:
            for uid in empty_history_uids:
                try:
                    os.remove(os.path.join(conf_dir, f"{uid}.json"))
                except Exception as e:
                    logger.error(f"Failed to remove empty history file {uid}: {e}")

        histories.sort(key=lambda x: x["timestamp"] if x["timestamp"] else "", reverse=True)
        return histories
    except Exception as e:
        logger.error(f"Error listing histories: {e}")
        return []
