"""Live2D chat history file storage (apps.live2d.engine.chat_history)."""

import json
import os
import threading
import time

import pytest

from apps.live2d.engine import chat_history

CONF = "test_conf"


@pytest.fixture(autouse=True)
def _history_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_history, "CHAT_HISTORY_DIR", str(tmp_path))
    return tmp_path


def _path(history_uid):
    return chat_history._get_safe_history_path(CONF, history_uid)


def test_concurrent_store_message_never_corrupts_file():
    """Interrupt handling stores two messages back to back on worker threads; the old
    read-modify-write without a lock left trailing bytes ("Extra data")."""
    uid = chat_history.create_new_history(CONF)
    threads = [
        threading.Thread(target=chat_history.store_message, args=(CONF, uid, "ai", f"訊息 {i} " + "字" * (i % 7) * 50))
        for i in range(40)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with open(_path(uid), encoding="utf-8") as f:
        data = json.load(f)  # raises on a corrupted file
    assert len([m for m in data if m["role"] == "ai"]) == 40


def test_atomic_write_leaves_no_temp_files():
    uid = chat_history.create_new_history(CONF)
    chat_history.store_message(CONF, uid, "human", "你好")
    leftovers = [n for n in os.listdir(os.path.dirname(_path(uid))) if n.startswith(".tmp-")]
    assert leftovers == []


def test_history_list_only_reads_requested_uids():
    mine = chat_history.create_new_history(CONF)
    chat_history.store_message(CONF, mine, "human", "我的問題")
    other = chat_history.create_new_history(CONF)
    chat_history.store_message(CONF, other, "human", "別人的問題")
    with open(_path("2020-01-01_broken"), "w", encoding="utf-8") as f:
        f.write('[{"role": "metadata"}]]garbage')

    histories = chat_history.get_history_list(CONF, [mine])
    assert [h["uid"] for h in histories] == [mine]
    assert histories[0]["latest_message"]["content"] == "我的問題"


def test_history_list_skips_empty_and_missing():
    empty = chat_history.create_new_history(CONF)
    assert chat_history.get_history_list(CONF, [empty, "does-not-exist"]) == []


def _age(uid_or_name, seconds, now):
    path = os.path.join(os.path.dirname(_path("x")), uid_or_name)
    os.utime(path, (now - seconds, now - seconds))


def test_prune_removes_expired_empty_corrupt_and_temp_files():
    now = time.time()
    day = 24 * 60 * 60

    recent = chat_history.create_new_history(CONF)
    chat_history.store_message(CONF, recent, "human", "昨天")
    old = chat_history.create_new_history(CONF)
    chat_history.store_message(CONF, old, "human", "兩個月前")
    stale_empty = chat_history.create_new_history(CONF)
    fresh_empty = chat_history.create_new_history(CONF)
    with open(_path("corrupt"), "w", encoding="utf-8") as f:
        f.write("[]]")
    conf_dir = os.path.dirname(_path("x"))
    open(os.path.join(conf_dir, ".tmp-leftover.json"), "w").close()

    _age(f"{recent}.json", 1 * day, now)
    _age(f"{old}.json", 60 * day, now)
    _age(f"{stale_empty}.json", 2 * day, now)
    _age("corrupt.json", 2 * day, now)
    _age(".tmp-leftover.json", 2 * 60 * 60, now)

    removed = chat_history.prune_histories(CONF, retention_days=30, now=now)

    remaining = set(os.listdir(conf_dir))
    assert remaining == {f"{recent}.json", f"{fresh_empty}.json"}
    assert removed == 4


def test_prune_disabled_with_zero_retention():
    uid = chat_history.create_new_history(CONF)
    now = time.time()
    _age(f"{uid}.json", 365 * 24 * 60 * 60, now)
    assert chat_history.prune_histories(CONF, retention_days=0, now=now) == 0
    assert os.path.exists(_path(uid))
