import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.divinations.models import DivinationSession
from apps.divinations.services import DomainError

from .models import AIMessage


def _category_meaning(session: DivinationSession) -> str:
    fortune = session.fortune
    field = f"{session.category}_meaning"
    return getattr(fortune, field, "") or fortune.general_meaning


def _system_prompt(session: DivinationSession) -> str:
    template = session.fortune_set.prompt_template.strip()
    if template:
        return template
    return (
        "你是傳統籤詩文化解說助手。只能根據提供的籤詩資料解釋，"
        "不得宣稱未來一定發生，不得代表神明，不得取代醫療、法律或財務專業意見。"
    )


def _interpret_user_prompt(session: DivinationSession) -> str:
    fortune = session.fortune
    casts = ", ".join(session.block_casts.values_list("result", flat=True))
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
擲筊結果：{casts}

請用繁體中文回答，包含：籤詩整體含義、與問題的關聯、當前情況分析、可採取的行動、應注意事項、文化體驗提醒。
""".strip()


def _chat(messages: list[dict[str, str]]) -> str:
    headers = {}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

    try:
        response = httpx.post(
            f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers=headers,
            json={"model": settings.LLM_MODEL, "messages": messages},
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise DomainError("AI_SERVICE_UNAVAILABLE", "AI 暫時無法使用，請稍後再試", 503) from exc


def interpret_session(session_uuid: str) -> DivinationSession:
    session = DivinationSession.objects.select_related("fortune_set", "fortune").get(session_uuid=session_uuid)
    if session.status == "completed" and session.ai_interpretation:
        return session
    if not session.confirmed or session.status != "confirmed" or not session.fortune_id:
        raise DomainError("INVALID_SESSION_STATE", "尚未取得聖筊，不能解籤", 409)

    system_prompt = _system_prompt(session)
    user_prompt = _interpret_user_prompt(session)
    content = _chat([{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}])

    with transaction.atomic():
        session = DivinationSession.objects.select_for_update().get(pk=session.pk)
        session.ai_interpretation = content
        session.status = "completed"
        session.completed_at = timezone.now()
        session.save(update_fields=["ai_interpretation", "status", "completed_at", "updated_at"])
        AIMessage.objects.bulk_create(
            [
                AIMessage(divination_session=session, role="system", content=system_prompt, model_name=settings.LLM_MODEL),
                AIMessage(divination_session=session, role="user", content=user_prompt, model_name=settings.LLM_MODEL),
                AIMessage(divination_session=session, role="assistant", content=content, model_name=settings.LLM_MODEL),
            ]
        )
    return session


def chat_about_session(session_uuid: str, message: str) -> str:
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
    return reply
