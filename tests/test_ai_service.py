import pytest

from apps.ai_service.models import AIMessage
from apps.ai_service.services import (
    _chat,
    chat_about_session,
    interpret_session,
    list_session_messages,
)
from apps.divinations.models import DivinationSession
from apps.fortunes.models import Fortune, FortuneSet


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


def test_chat_allows_empty_api_key_for_local_models(settings, monkeypatch):
    calls = []
    settings.LLM_API_KEY = ""
    settings.LLM_BASE_URL = "http://localhost:1234/v1"
    settings.LLM_MODEL = "local-model"

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr("apps.ai_service.services.httpx.post", fake_post)

    assert _chat([{"role": "user", "content": "hi"}]) == "ok"
    assert calls[0]["headers"] == {}


def test_chat_sends_auth_header_when_api_key_exists(settings, monkeypatch):
    calls = []
    settings.LLM_API_KEY = "secret"

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr("apps.ai_service.services.httpx.post", fake_post)

    _chat([{"role": "user", "content": "hi"}])

    assert calls[0]["headers"] == {"Authorization": "Bearer secret"}


@pytest.mark.django_db
def test_interpret_is_idempotent_after_completed(monkeypatch):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=1, poem="詩")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        question="測試",
        category="career",
        interaction_mode="click",
        status="completed",
        confirmed=True,
        ai_interpretation="已解籤",
    )
    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: "不應呼叫")

    result = interpret_session(session.session_uuid)

    assert result.ai_interpretation == "已解籤"


@pytest.mark.django_db
def test_chat_keeps_context_and_returns_display_messages(monkeypatch):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=2, poem="詩")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        question="最近適合換工作嗎？",
        category="career",
        interaction_mode="click",
        status="completed",
        confirmed=True,
        ai_interpretation="初始解籤",
    )
    AIMessage.objects.create(divination_session=session, role="system", content="系統")
    AIMessage.objects.create(divination_session=session, role="user", content="隱藏解籤 prompt")
    AIMessage.objects.create(divination_session=session, role="assistant", content="初始解籤")
    calls = []

    def fake_chat(messages):
        calls.append(messages)
        return "可以先盤點履歷"

    monkeypatch.setattr("apps.ai_service.services._interpret_user_prompt", lambda session: "隱藏解籤 prompt")
    monkeypatch.setattr("apps.ai_service.services._chat", fake_chat)

    data = chat_about_session(session.session_uuid, "我該怎麼準備？")

    assert data["reply"] == "可以先盤點履歷"
    assert [message["role"] for message in data["messages"]] == ["user", "assistant"]
    assert data["messages"][0]["content"] == "我該怎麼準備？"
    assert calls[0][-1] == {"role": "user", "content": "我該怎麼準備？"}
    assert {"role": "assistant", "content": "初始解籤"} in calls[0]


@pytest.mark.django_db
def test_list_session_messages_hides_initial_interpretation_prompt(monkeypatch):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=3, poem="詩")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        question="最近適合換工作嗎？",
        category="career",
        interaction_mode="click",
        status="completed",
        confirmed=True,
        ai_interpretation="初始解籤",
    )
    AIMessage.objects.create(divination_session=session, role="system", content="系統")
    AIMessage.objects.create(divination_session=session, role="user", content="隱藏解籤 prompt")
    AIMessage.objects.create(divination_session=session, role="assistant", content="初始解籤")
    AIMessage.objects.create(divination_session=session, role="user", content="追問")
    monkeypatch.setattr("apps.ai_service.services._interpret_user_prompt", lambda session: "隱藏解籤 prompt")

    messages = list_session_messages(session.session_uuid)

    assert [message["content"] for message in messages] == ["追問"]
