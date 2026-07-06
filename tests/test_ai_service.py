import pytest

from apps.ai_service.services import _chat, interpret_session
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
