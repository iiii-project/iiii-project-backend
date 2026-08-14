from types import SimpleNamespace

import pytest

from apps.ai_service.models import AIMessage
from apps.ai_service.services import (
    _chat,
    chat_about_session,
    interpret_session,
    list_session_messages,
    prewarm_interpretation,
)
from apps.divinations.models import DivinationSession
from apps.divinations.services import DomainError
from apps.fortunes.models import Fortune, FortuneSet


class FakeResponse:
    def __init__(self, content="ok"):
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self.content}}], "usage": {"total_tokens": 3}}


class FakeSpan:
    def __init__(self):
        self.input = None
        self.output = None
        self.model = None
        self.provider = None
        self.usage = None


class FakeSpanContext:
    def __init__(self, span):
        self.span = span

    def __enter__(self):
        return self.span

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_chat_allows_empty_api_key_for_local_models(settings, monkeypatch):
    calls = []
    settings.OPIK_ENABLED = False
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
    settings.OPIK_ENABLED = False
    settings.LLM_API_KEY = "secret"

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr("apps.ai_service.services.httpx.post", fake_post)

    _chat([{"role": "user", "content": "hi"}])

    assert calls[0]["headers"] == {"Authorization": "Bearer secret"}


def test_chat_logs_opik_span_when_enabled(settings, monkeypatch):
    settings.OPIK_ENABLED = True
    settings.OPIK_PROJECT_NAME = "ai-fortune"
    settings.LLM_MODEL = "local-model"
    span = FakeSpan()
    calls = []

    def fake_span(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeSpanContext(span)

    monkeypatch.setattr("apps.ai_service.services.opik", SimpleNamespace(start_as_current_span=fake_span))
    monkeypatch.setattr("apps.ai_service.services.httpx.post", lambda *args, **kwargs: FakeResponse())

    assert _chat([{"role": "user", "content": "hi"}]) == "ok"

    assert calls == [(("fortune-llm-chat",), {"type": "llm", "project_name": "ai-fortune"})]
    assert span.input == {"messages": [{"role": "user", "content": "hi"}]}
    assert span.output == {"content": "ok"}
    assert span.model == "local-model"
    assert span.provider == "openai-compatible"
    assert span.usage == {"total_tokens": 3}


def test_chat_rejects_empty_model_reply(settings, monkeypatch):
    settings.OPIK_ENABLED = False
    monkeypatch.setattr("apps.ai_service.services.httpx.post", lambda *args, **kwargs: FakeResponse(""))

    with pytest.raises(Exception) as exc_info:
        _chat([{"role": "user", "content": "hi"}])

    assert exc_info.value.default_code == "AI_SERVICE_UNAVAILABLE"


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
def test_interpret_retries_completed_session_without_interpretation(monkeypatch):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=4, poem="詩")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        question="測試",
        category="career",
        interaction_mode="click",
        status="completed",
        confirmed=True,
        ai_interpretation="",
    )
    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: "補回解籤")

    result = interpret_session(session.session_uuid)

    assert result.status == "completed"
    assert result.ai_interpretation == "補回解籤"


@pytest.mark.django_db
def test_interpret_rejects_concurrent_call_already_in_progress(monkeypatch):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=5, poem="詩")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        question="測試",
        category="career",
        interaction_mode="click",
        status="interpreting",
        confirmed=True,
    )
    calls = []
    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: calls.append(messages) or "不應呼叫")

    with pytest.raises(DomainError) as exc_info:
        interpret_session(session.session_uuid)

    assert exc_info.value.default_code == "INTERPRETATION_IN_PROGRESS"
    assert calls == []


@pytest.mark.django_db
def test_interpret_releases_claim_when_llm_call_fails(monkeypatch):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=6, poem="詩")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        question="測試",
        category="career",
        interaction_mode="click",
        status="confirmed",
        confirmed=True,
    )

    def failing_chat(messages):
        raise DomainError("AI_SERVICE_UNAVAILABLE", "AI 暫時無法使用，請稍後再試", 503)

    monkeypatch.setattr("apps.ai_service.services._chat", failing_chat)

    with pytest.raises(DomainError):
        interpret_session(session.session_uuid)

    session.refresh_from_db()
    assert session.status == "confirmed"

    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: "重試成功")
    result = interpret_session(session.session_uuid)

    assert result.status == "completed"
    assert result.ai_interpretation == "重試成功"


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
    AIMessage.objects.create(divination_session=session, role="system", content="系統", is_hidden=True)
    AIMessage.objects.create(divination_session=session, role="user", content="隱藏解籤 prompt", is_hidden=True)
    AIMessage.objects.create(divination_session=session, role="assistant", content="初始解籤", is_hidden=True)
    calls = []

    def fake_chat(messages):
        calls.append(messages)
        return "可以先盤點履歷"

    monkeypatch.setattr("apps.ai_service.services._chat", fake_chat)

    data = chat_about_session(session.session_uuid, "我該怎麼準備？")

    assert data["reply"] == "可以先盤點履歷"
    assert [message["role"] for message in data["messages"]] == ["user", "assistant"]
    assert data["messages"][0]["content"] == "我該怎麼準備？"
    assert calls[0][-1] == {"role": "user", "content": "我該怎麼準備？"}
    assert {"role": "assistant", "content": "初始解籤"} in calls[0]


@pytest.mark.django_db
def test_chat_reports_remaining_messages_and_stops_at_limit(monkeypatch):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=4, poem="詩")
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
    AIMessage.objects.create(divination_session=session, role="system", content="系統", is_hidden=True)
    AIMessage.objects.create(divination_session=session, role="user", content="隱藏解籤 prompt", is_hidden=True)
    AIMessage.objects.create(divination_session=session, role="assistant", content="初始解籤", is_hidden=True)
    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: "回覆")

    for expected_remaining in [4, 3, 2, 1, 0]:
        data = chat_about_session(session.session_uuid, "追問")
        assert data["remaining_messages"] == expected_remaining

    with pytest.raises(DomainError):
        chat_about_session(session.session_uuid, "第六次追問")


@pytest.mark.django_db
def test_list_session_messages_hides_initial_interpretation_prompt():
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
    AIMessage.objects.create(divination_session=session, role="system", content="系統", is_hidden=True)
    AIMessage.objects.create(divination_session=session, role="user", content="隱藏解籤 prompt", is_hidden=True)
    AIMessage.objects.create(divination_session=session, role="assistant", content="初始解籤", is_hidden=True)
    AIMessage.objects.create(divination_session=session, role="user", content="追問")

    messages = list_session_messages(session.session_uuid)

    assert [message["content"] for message in messages] == ["追問"]


def _confirmed_session(number, question="最近適合換工作嗎？"):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=number, poem="詩")
    return DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        question=question,
        category="career",
        interaction_mode="click",
        status="confirmed",
        confirmed=True,
    )


@pytest.mark.django_db
def test_prewarmed_interpretation_is_reused_without_calling_llm_again(monkeypatch, settings):
    """抽籤時預熱好的解籤，擲筊後要直接拿來用，不再多跑一次 LLM。"""
    settings.INTERPRET_PREWARM_ENABLED = True
    session = _confirmed_session(number=11)
    calls = []
    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: calls.append(messages) or "預熱好的解籤")

    # 抽籤那一刻的預熱：prompt 不含擲筊結果，籤詩/問題/主題到齊即可先跑
    prewarm_interpretation(session)
    result = interpret_session(session.session_uuid)

    assert result.ai_interpretation == "預熱好的解籤"
    assert len(calls) == 1  # 只有預熱那一次


@pytest.mark.django_db
def test_prewarm_is_ignored_after_redrawing_a_different_fortune(monkeypatch, settings):
    """非聖筊會重抽籤，前一支籤的預熱結果不可以被拿去解新的籤。"""
    settings.INTERPRET_PREWARM_ENABLED = True
    session = _confirmed_session(number=12)
    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: "舊籤的解籤")
    prewarm_interpretation(session)

    # 重抽：換成另一支籤（模擬 cast_blocks 擲出非聖筊後重新 draw）
    session.fortune = Fortune.objects.create(fortune_set=session.fortune_set, number=13, poem="另一首")
    session.save(update_fields=["fortune"])
    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: "新籤的解籤")

    result = interpret_session(session.session_uuid)

    assert result.ai_interpretation == "新籤的解籤"


@pytest.mark.django_db
def test_prewarm_failure_falls_back_to_generating_on_demand(monkeypatch, settings):
    """預熱失敗（例如 LLM 暫時掛掉）不能拖垮解籤，照原路重跑一次就好。"""
    settings.INTERPRET_PREWARM_ENABLED = True
    session = _confirmed_session(number=14)

    def boom(messages):
        raise RuntimeError("LLM 掛了")

    monkeypatch.setattr("apps.ai_service.services._chat", boom)
    prewarm_interpretation(session)
    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: "現場生成的解籤")

    result = interpret_session(session.session_uuid)

    assert result.ai_interpretation == "現場生成的解籤"
