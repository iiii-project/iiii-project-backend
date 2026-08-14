"""Acceptance tests for STORY-003: Chat Record Ownership Verification.

Covers all four required behaviors from STORY-003-BACKEND-REQUEST.md:
1. GET /divinations/{session_id}/chat/ requires an authenticated user.
2. Chat content is returned only when the authenticated user owns the session.
3. An unauthenticated request returns no chat content.
4. An authenticated non-owner request returns no chat content, and the response
   is indistinguishable from a request for a session_id that does not exist.
"""

import uuid

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.divinations.models import DivinationSession
from apps.fortunes.models import Fortune, FortuneSet


def _completed_owned_session(username):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=1000 + hash(username) % 1000, poem="詩")
    owner = User.objects.create_user(username=username, password="A-strong-password-1")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        user=owner,
        question="這是我的私人問題",
        category="career",
        interaction_mode="click",
        status="completed",
        confirmed=True,
        ai_interpretation="已解籤",
    )
    return owner, session


@pytest.mark.django_db
def test_chat_get_rejects_unauthenticated_request():
    _, session = _completed_owned_session("story003-owner-1")

    response = APIClient().get(f"/api/v1/divinations/{session.session_uuid}/chat/")

    assert response.status_code == 401
    assert response.json()["success"] is False


@pytest.mark.django_db
def test_chat_get_returns_content_for_owner():
    owner, session = _completed_owned_session("story003-owner-2")
    client = APIClient()
    client.force_authenticate(owner)

    response = client.get(f"/api/v1/divinations/{session.session_uuid}/chat/")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "messages" in response.json()["data"]


@pytest.mark.django_db
def test_chat_get_rejects_authenticated_non_owner():
    _, session = _completed_owned_session("story003-owner-3")
    stranger = User.objects.create_user(username="story003-stranger", password="A-strong-password-1")
    client = APIClient()
    client.force_authenticate(stranger)

    response = client.get(f"/api/v1/divinations/{session.session_uuid}/chat/")

    assert response.status_code == 404
    assert response.json()["success"] is False


@pytest.mark.django_db
def test_chat_get_non_owner_response_matches_missing_session_response():
    _, session = _completed_owned_session("story003-owner-4")
    stranger = User.objects.create_user(username="story003-stranger-2", password="A-strong-password-1")
    client = APIClient()
    client.force_authenticate(stranger)

    non_owner_response = client.get(f"/api/v1/divinations/{session.session_uuid}/chat/")
    missing_response = client.get(f"/api/v1/divinations/{uuid.uuid4()}/chat/")

    assert non_owner_response.status_code == missing_response.status_code == 404
    assert non_owner_response.json() == missing_response.json()


@pytest.mark.django_db
def test_chat_post_still_allows_anonymous_session_owner(monkeypatch):
    """POST is out of scope for STORY-003 and must keep its existing behavior."""
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=1999, poem="詩")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        question="匿名問題",
        category="career",
        interaction_mode="click",
        status="completed",
        confirmed=True,
        ai_interpretation="已解籤",
    )
    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: "匿名可以繼續對話")

    response = APIClient().post(
        f"/api/v1/divinations/{session.session_uuid}/chat/", {"message": "追問"}, format="json"
    )

    assert response.status_code == 200
    assert response.json()["data"]["reply"] == "匿名可以繼續對話"


@pytest.mark.django_db
def test_chat_post_rejects_message_over_250_chars():
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=2000, poem="詩")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        question="匿名問題",
        category="career",
        interaction_mode="click",
        status="completed",
        confirmed=True,
        ai_interpretation="已解籤",
    )

    response = APIClient().post(
        f"/api/v1/divinations/{session.session_uuid}/chat/", {"message": "問" * 251}, format="json"
    )

    assert response.status_code == 400
