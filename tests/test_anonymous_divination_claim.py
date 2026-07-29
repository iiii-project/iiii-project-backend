"""Acceptance tests for the anonymous divination claim endpoint.

Covers the rules in ANONYMOUS_DIVINATION_CLAIM_API.md:
1. Requires an authenticated user.
2. Only an anonymous (user=null) session can be claimed.
3. Claiming sets `user` and clears `anonymous_user_id`.
4. Re-claiming a session already owned by the caller succeeds without error.
5. Claiming someone else's, a nonexistent, or a non-anonymous session_id
   returns the same 404 NOT_FOUND body in all cases.
"""

import uuid

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.divinations.models import DivinationSession
from apps.fortunes.models import Fortune, FortuneSet


def _anonymous_session(anonymous_user_id="guest-browser-id"):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=hash(anonymous_user_id) % 100000, poem="詩")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        fortune=fortune,
        anonymous_user_id=anonymous_user_id,
        question="今年轉職是否合適？",
        category="career",
        interaction_mode="click",
        status="completed",
        confirmed=True,
        ai_interpretation="已解籤",
    )
    return session


@pytest.mark.django_db
def test_claim_requires_authentication():
    session = _anonymous_session()

    response = APIClient().post(f"/api/v1/divinations/{session.session_uuid}/claim/")

    assert response.status_code == 401
    assert response.json()["success"] is False


@pytest.mark.django_db
def test_claim_binds_anonymous_session_to_caller_and_clears_anonymous_id():
    session = _anonymous_session(anonymous_user_id="guest-browser-id")
    user = User.objects.create_user(username="claim-owner-1", password="A-strong-password-1")
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(f"/api/v1/divinations/{session.session_uuid}/claim/")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["session_id"] == str(session.session_uuid)
    assert body["data"]["anonymous_user_id"] == ""

    session.refresh_from_db()
    assert session.user_id == user.id
    assert session.anonymous_user_id == ""


@pytest.mark.django_db
def test_reclaiming_own_session_is_idempotent():
    session = _anonymous_session()
    user = User.objects.create_user(username="claim-owner-2", password="A-strong-password-1")
    client = APIClient()
    client.force_authenticate(user)

    first = client.post(f"/api/v1/divinations/{session.session_uuid}/claim/")
    second = client.post(f"/api/v1/divinations/{session.session_uuid}/claim/")

    assert first.status_code == second.status_code == 200
    session.refresh_from_db()
    assert session.user_id == user.id


@pytest.mark.django_db
def test_claim_rejects_session_already_owned_by_someone_else():
    session = _anonymous_session()
    owner = User.objects.create_user(username="claim-owner-3", password="A-strong-password-1")
    stranger = User.objects.create_user(username="claim-stranger-1", password="A-strong-password-1")
    owner_client = APIClient()
    owner_client.force_authenticate(owner)
    owner_client.post(f"/api/v1/divinations/{session.session_uuid}/claim/")

    stranger_client = APIClient()
    stranger_client.force_authenticate(stranger)
    response = stranger_client.post(f"/api/v1/divinations/{session.session_uuid}/claim/")

    assert response.status_code == 404
    assert response.json()["success"] is False

    session.refresh_from_db()
    assert session.user_id == owner.id


@pytest.mark.django_db
def test_claim_missing_session_id_returns_same_404_as_owned_session():
    session = _anonymous_session()
    owner = User.objects.create_user(username="claim-owner-4", password="A-strong-password-1")
    stranger = User.objects.create_user(username="claim-stranger-2", password="A-strong-password-1")
    owner_client = APIClient()
    owner_client.force_authenticate(owner)
    owner_client.post(f"/api/v1/divinations/{session.session_uuid}/claim/")

    stranger_client = APIClient()
    stranger_client.force_authenticate(stranger)

    already_owned_response = stranger_client.post(f"/api/v1/divinations/{session.session_uuid}/claim/")
    missing_response = stranger_client.post(f"/api/v1/divinations/{uuid.uuid4()}/claim/")

    assert already_owned_response.status_code == missing_response.status_code == 404
    assert already_owned_response.json() == missing_response.json()


@pytest.mark.django_db
def test_claim_rejects_non_anonymous_session_created_by_login():
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    owner = User.objects.create_user(username="claim-owner-5", password="A-strong-password-1")
    session = DivinationSession.objects.create(
        fortune_set=fortune_set,
        user=owner,
        question="這是登入直接建立的紀錄",
        category="career",
        interaction_mode="click",
        status="created",
    )
    stranger = User.objects.create_user(username="claim-stranger-3", password="A-strong-password-1")
    client = APIClient()
    client.force_authenticate(stranger)

    response = client.post(f"/api/v1/divinations/{session.session_uuid}/claim/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_claim_allows_any_session_status():
    session = _anonymous_session()
    session.status = "created"
    session.confirmed = False
    session.ai_interpretation = ""
    session.save()
    user = User.objects.create_user(username="claim-owner-6", password="A-strong-password-1")
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(f"/api/v1/divinations/{session.session_uuid}/claim/")

    assert response.status_code == 200
