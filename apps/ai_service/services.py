import os
import threading
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from contextlib import contextmanager

import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.divinations.models import DivinationSession
from config.exceptions import DomainError

from .models import AIMessage

try:
    import opik
except ImportError:  # pragma: no cover - optional observability dependency
    opik = None


def _message_data(message: AIMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at,
    }


def _category_meaning(session: DivinationSession) -> str:
    fortune = session.fortune
    field = f"{session.category}_meaning"
    return getattr(fortune, field, "") or fortune.general_meaning


def _system_prompt(session: DivinationSession) -> str:
    template = session.fortune_set.prompt_template.strip()
    if template:
        return template
    return (
        "你是親切且專業的傳統籤詩文化解說助手。請只根據提供的籤詩資料回答，"
        "以尊重、平易近人的態度說明籤詩含義，並嚴格只使用繁體中文回覆。"
        "回覆時請提醒使用者本內容僅供文化體驗與參考，不能取代專業意見。"
    )


def _interpret_user_prompt(session: DivinationSession) -> str:
    fortune = session.fortune
    return f"""
籤系：{session.fortune_set.name}
使用者問題：{session.question}
求籤主題：{session.category}
籤號：{fortune.number}
籤名：{fortune.title}
天干地支：{fortune.ganzhi}
吉凶分類：{fortune.fortune_level}
籤詩原文：{fortune.poem}
白話翻譯：{fortune.translation}
籤詩典故：{fortune.story}
一般解釋：{fortune.general_meaning}
對應主題解釋：{_category_meaning(session)}

請用繁體中文回答，包含：籤詩整體含義、與問題的關聯、當前情況分析、可採取的行動、應注意事項、文化體驗提醒。
""".strip()


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _trust_env_for_llm() -> bool:
    """本機模型不要經過系統代理。

    httpx 預設 trust_env=True，在 macOS 上會去讀「系統設定 → 網路 → 代理伺服器」
    （透過 urllib 的 getproxies()）。只要那裡設了 HTTP 代理，連
    http://localhost:1234 這種本機請求都會被送去代理，然後回 404/400——
    表現出來就是「AI 解籤暫時無法使用」，但模型其實好好地在跑。
    curl 不讀那份設定，所以手動測都會過，只有後端打不到，很難查。

    因此：LLM 在 loopback 位址時一律略過環境代理；指向外部主機時才照原本的行為
    （企業環境可能真的需要代理）。
    """
    host = httpx.URL(settings.LLM_BASE_URL).host
    return host not in _LOOPBACK_HOSTS


def _chat(messages: list[dict[str, str]]) -> str:
    headers = {}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

    try:
        with _llm_span(messages) as span:
            response = httpx.post(
                f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
                headers=headers,
                json={"model": settings.LLM_MODEL, "messages": messages},
                timeout=settings.LLM_TIMEOUT_SECONDS,
                trust_env=_trust_env_for_llm(),
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not content.strip():
                raise ValueError
            if span:
                span.output = {"content": content}
                span.usage = data.get("usage")
            return content
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise DomainError("AI_SERVICE_UNAVAILABLE", "AI 暫時無法使用，請稍後再試", 503) from exc


@contextmanager
def _llm_span(messages: list[dict[str, str]]):
    if opik is None or not settings.OPIK_ENABLED:
        yield None
        return

    try:
        span_context = opik.start_as_current_span(
            "fortune-llm-chat",
            type="llm",
            project_name=settings.OPIK_PROJECT_NAME,
        )
        span = span_context.__enter__()
    except Exception:
        yield None
        return

    span.input = {"messages": messages}
    span.model = settings.LLM_MODEL
    span.provider = "openai-compatible"

    try:
        yield span
    except BaseException as exc:
        if span_context.__exit__(type(exc), exc, exc.__traceback__):
            return
        raise
    else:
        span_context.__exit__(None, None, None)


# ── 解籤預熱 ────────────────────────────────────────────────────────────────
# 本地 LLM 生成一份解籤實測要 ~21 秒，而使用者在抽到籤之後還要擲筊、看筊杯動畫、
# 看領籤過場，這段時間原本整個空著。抽籤成功的那一刻籤詩就已經定了，解籤 prompt
# 需要的資料（籤詩、問題、主題）全部到齊，且不含擲筊結果，因此這裡可以在抽籤完成
# 時就直接把 LLM 跑起來，等使用者真的擲出聖筊呼叫 interpret 時，多半直接取用
# 預熱結果，省掉整段等待。
#
# 預熱是純粹的加速手段：拿不到（換 worker、還沒跑完、擲筊擲很久導致逾時、或生成
# 失敗）就照原本的路徑重新生成一次，行為與沒有預熱時完全相同。prompt 內容與正式
# 路徑一致，所以 AIMessage 紀錄不會出現兩種版本。
_PREWARM_MAX_WORKERS = int(os.getenv("INTERPRET_PREWARM_WORKERS", "2"))
_PREWARM_KEEP = 64
_prewarm_pool: ThreadPoolExecutor | None = None
_prewarm_jobs: "OrderedDict[str, _PrewarmJob]" = OrderedDict()
_prewarm_lock = threading.Lock()


@dataclass(frozen=True)
class _PrewarmJob:
    fortune_id: int
    # 影響解籤內容的條件：換籤或改題目就不能再用這份預熱結果
    signature: tuple
    user_prompt: str
    future: "Future[str]"


def _prewarm_signature(session: DivinationSession) -> tuple:
    return (session.fortune_id, session.question, tuple(session.categories or []), session.category)


def _pool() -> ThreadPoolExecutor:
    global _prewarm_pool
    if _prewarm_pool is None:
        _prewarm_pool = ThreadPoolExecutor(
            max_workers=_PREWARM_MAX_WORKERS,
            thread_name_prefix="interpret-prewarm",
        )
    return _prewarm_pool


def prewarm_interpretation(session: DivinationSession) -> None:
    """抽籤完成後呼叫：在背景先把這支籤的解籤生成出來。失敗一律吞掉。"""
    if not settings.INTERPRET_PREWARM_ENABLED or not session.fortune_id:
        return
    key = str(session.session_uuid)
    try:
        system_prompt = _system_prompt(session)
        user_prompt = _interpret_user_prompt(session)
    except Exception:  # 資料不全就別預熱，正式路徑會照樣報錯
        return

    signature = _prewarm_signature(session)
    with _prewarm_lock:
        existing = _prewarm_jobs.get(key)
        # 同一支籤、同一個問題已經在跑（或跑完）就不重複送
        if existing and existing.signature == signature:
            return
        while len(_prewarm_jobs) >= _PREWARM_KEEP:
            _prewarm_jobs.popitem(last=False)
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        try:
            future = _pool().submit(_chat, messages)
        except RuntimeError:  # 程序正在關閉
            return
        # 沒人來取也不要在關站時噴 unraisable exception
        future.add_done_callback(lambda done: done.exception() and None)
        _prewarm_jobs[key] = _PrewarmJob(session.fortune_id, signature, user_prompt, future)


def _take_prewarmed(session: DivinationSession) -> tuple[str, str] | None:
    """取用預熱結果，回傳 (實際送出的 user prompt, 解籤內容)。

    只有同一支籤、同一個問題才算命中；重抽籤或中途改題目都會落空，
    落空就回 None 讓呼叫端照原路現場生成。
    """
    with _prewarm_lock:
        job = _prewarm_jobs.get(str(session.session_uuid))
        if not job or job.signature != _prewarm_signature(session):
            return None
        _prewarm_jobs.pop(str(session.session_uuid), None)
    try:
        # 已經在背景跑了一段時間，這裡最多再等滿原本的 LLM 逾時
        content = job.future.result(timeout=settings.LLM_TIMEOUT_SECONDS)
    except Exception:
        return None
    if not content or not content.strip():
        return None
    return job.user_prompt, content


def interpret_session(session_uuid: str, request_data: dict | None = None) -> DivinationSession:
    session = DivinationSession.objects.select_related("fortune_set", "fortune").get(session_uuid=session_uuid)
    if session.status == "completed" and session.ai_interpretation:
        return session
    if session.status == "interpreting":
        raise DomainError("INTERPRETATION_IN_PROGRESS", "解籤正在處理中，請稍後再試", 409)
    if not session.confirmed or session.status not in {"confirmed", "completed"} or not session.fortune_id:
        raise DomainError("INVALID_SESSION_STATE", "尚未取得聖筊，不能解籤", 409)

    # Atomically claim the session before calling the (slow) LLM so a concurrent
    # duplicate request (double-click, frontend retry after timeout) can't also
    # pass the checks above and trigger a second LLM call / duplicate messages.
    original_status = session.status
    claimed = DivinationSession.objects.filter(pk=session.pk, status=original_status).update(
        status="interpreting", updated_at=timezone.now()
    )
    if not claimed:
        raise DomainError("INTERPRETATION_IN_PROGRESS", "解籤正在處理中，請稍後再試", 409)
    session.status = "interpreting"

    if request_data:
        updated_fields = []
        question = request_data.get("question")
        categories = request_data.get("categories")

        if question and question != session.question:
            session.question = question
            updated_fields.append("question")
        if categories and categories != session.categories:
            session.categories = categories
            session.category = categories[0]
            updated_fields.append("categories")
            updated_fields.append("category")

        if updated_fields:
            updated_fields.append("updated_at")
            session.save(update_fields=updated_fields)

    system_prompt = _system_prompt(session)
    try:
        # 抽籤時就開始生成的那一份；沒有命中才現場跑一次
        prewarmed = _take_prewarmed(session)
        if prewarmed:
            user_prompt, content = prewarmed
        else:
            user_prompt = _interpret_user_prompt(session)
            content = _chat([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])
    except Exception:
        # Release the claim so a subsequent retry isn't stuck in "interpreting" forever.
        DivinationSession.objects.filter(pk=session.pk, status="interpreting").update(
            status=original_status, updated_at=timezone.now()
        )
        raise

    with transaction.atomic():
        session = DivinationSession.objects.select_for_update().get(pk=session.pk)
        session.ai_interpretation = content
        session.status = "completed"
        session.completed_at = timezone.now()
        session.save(update_fields=["ai_interpretation", "status", "completed_at", "updated_at"])
        AIMessage.objects.bulk_create(
            [
                AIMessage(
                    divination_session=session,
                    role="system",
                    content=system_prompt,
                    model_name=settings.LLM_MODEL,
                    is_hidden=True,
                ),
                AIMessage(
                    divination_session=session,
                    role="user",
                    content=user_prompt,
                    model_name=settings.LLM_MODEL,
                    is_hidden=True,
                ),
                AIMessage(
                    divination_session=session,
                    role="assistant",
                    content=content,
                    model_name=settings.LLM_MODEL,
                    is_hidden=True,
                ),
            ]
        )
    return session


def list_session_messages(session_uuid: str) -> list[dict]:
    session = DivinationSession.objects.select_related("fortune_set", "fortune").get(session_uuid=session_uuid)
    if session.status != "completed":
        raise DomainError("INVALID_SESSION_STATE", "解籤完成後才能聊天", 409)

    messages = session.ai_messages.exclude(role="system").filter(is_hidden=False)
    return [_message_data(message) for message in messages]


def chat_about_session(session_uuid: str, message: str) -> dict:
    session = DivinationSession.objects.select_related("fortune_set", "fortune").get(session_uuid=session_uuid)
    if session.status != "completed":
        raise DomainError("INVALID_SESSION_STATE", "解籤完成後才能聊天", 409)

    messages = [{"role": "system", "content": _system_prompt(session)}]
    history = list(session.ai_messages.exclude(role="system").order_by("-created_at")[:10])
    messages.extend({"role": item.role, "content": item.content} for item in reversed(history))
    messages.append({"role": "user", "content": message})
    reply = _chat(messages)

    AIMessage.objects.bulk_create(
        [
            AIMessage(divination_session=session, role="user", content=message, model_name=settings.LLM_MODEL),
            AIMessage(divination_session=session, role="assistant", content=reply, model_name=settings.LLM_MODEL),
        ]
    )
    return {"reply": reply, "messages": list_session_messages(session_uuid)}
