"""JSON-file-backed conversation history, one file per (conf_uid, history_uid).

Ported from upstream open_llm_vtuber's chat_history_manager.py. Trimmed to the
functions actually used by the single-conversation flow (no modify_latest_message /
rename_history_file). Rooted under paths.CHAT_HISTORY_DIR instead of a bare relative
"chat_history" path, so it no longer depends on the process's current working directory.

These are synchronous, blocking file I/O — call sites in async code must wrap calls
with `await asyncio.to_thread(...)`.

Because those calls run on worker threads, two writes to the same history can happen at
once (e.g. an interrupt stores the cut-off reply and "[Interrupted by user]" back to
back). Every read-modify-write therefore holds a per-file lock, and files are replaced
atomically (write to a temp file, then os.replace) so a reader or a crash never sees a
half-written file.
"""

import json
import os
import re
import tempfile
import threading
import time
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


_locks_guard = threading.Lock()
_file_locks: dict[str, threading.Lock] = {}


def _lock_for(filepath: str) -> threading.Lock:
    with _locks_guard:
        lock = _file_locks.get(filepath)
        if lock is None:
            lock = _file_locks[filepath] = threading.Lock()
        return lock


def _forget_lock(filepath: str) -> None:
    with _locks_guard:
        _file_locks.pop(filepath, None)


def _atomic_write_json(filepath: str, data) -> None:
    """Write JSON to a temp file in the same directory, then atomically swap it in."""
    directory = os.path.dirname(filepath)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, filepath)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


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
        _atomic_write_json(filepath, initial_data)
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
    new_item = {"role": role, "timestamp": datetime.now().isoformat(timespec="seconds"), "content": content}
    if name is not None:
        new_item["name"] = name
    if avatar is not None:
        new_item["avatar"] = avatar

    with _lock_for(filepath):
        history_data = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
            except Exception:
                logger.error(f"Failed to load history file: {filepath}")
        history_data.append(new_item)
        _atomic_write_json(filepath, history_data)


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
        with _lock_for(filepath):
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
    except Exception as e:
        logger.error(f"Failed to delete history file: {e}")
    finally:
        _forget_lock(filepath)
    return False


def get_history_list(conf_uid: str, history_uids) -> List[dict]:
    """Summaries of the given histories only (the ones this connection owns).

    Deliberately does not scan the whole directory: every connection shares it, and
    reading every file on each connect got slower as history files piled up.
    """
    if not conf_uid:
        return []

    histories = []
    for history_uid in history_uids:
        try:
            filepath = _get_safe_history_path(conf_uid, history_uid)
            if not os.path.exists(filepath):
                continue
            with open(filepath, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except Exception as e:
            logger.error(f"Error reading history file {history_uid}: {e}")
            continue
        actual_messages = [msg for msg in messages if msg.get("role") != "metadata"]
        if not actual_messages:
            continue
        latest_message = actual_messages[-1]
        histories.append(
            {
                "uid": history_uid,
                "latest_message": latest_message,
                "timestamp": latest_message.get("timestamp"),
            }
        )

    histories.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    return histories


_EMPTY_HISTORY_GRACE_SECONDS = 24 * 60 * 60
_TMP_FILE_GRACE_SECONDS = 60 * 60


def prune_histories(conf_uid: str, retention_days: int, now: float | None = None) -> int:
    """Delete history files older than `retention_days`, plus leftovers that are never
    read again: empty (metadata-only) histories older than a day and stray temp files
    from an interrupted atomic write. Returns how many files were removed."""
    if not conf_uid or retention_days <= 0:
        return 0

    now = time.time() if now is None else now
    cutoff = now - retention_days * 24 * 60 * 60
    conf_dir = _ensure_conf_dir(conf_uid)
    removed = 0

    for filename in os.listdir(conf_dir):
        filepath = os.path.join(conf_dir, filename)
        try:
            mtime = os.path.getmtime(filepath)
            if filename.startswith(".tmp-"):
                expired = mtime < now - _TMP_FILE_GRACE_SECONDS
            elif filename.endswith(".json"):
                expired = mtime < cutoff or (
                    mtime < now - _EMPTY_HISTORY_GRACE_SECONDS and _is_empty_history(filepath)
                )
            else:
                continue
            if expired:
                with _lock_for(filepath):
                    os.remove(filepath)
                _forget_lock(filepath)
                removed += 1
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.error(f"Failed to prune history file {filename}: {e}")

    if removed:
        logger.info(f"Pruned {removed} old chat history file(s)")
    return removed


def _is_empty_history(filepath: str) -> bool:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            messages = json.load(f)
    except Exception:
        # 讀不起來的壞檔也不會再被讀取，跟空紀錄一樣過一天就清掉
        return True
    return not any(msg.get("role") != "metadata" for msg in messages)
