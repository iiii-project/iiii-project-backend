import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.divinations.models import DivinationSession
from apps.fortunes.models import FortuneSet


@pytest.mark.django_db
def test_register_returns_jwt_and_authenticated_history_is_owner_scoped():
    client = APIClient()
    response = client.post(
        "/api/v1/auth/register/",
        {"username": "temple-user", "email": "temple@example.com", "password": "A-strong-password-123"},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["user"]["username"] == "temple-user"
    assert payload["access"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {payload['access']}")
    assert client.get("/api/v1/auth/me/").json()["data"]["username"] == "temple-user"

    fortune_set = FortuneSet.objects.create(code="TEST_SET", name="Test set")
    user = get_user_model().objects.get(username="temple-user")
    other_user = get_user_model().objects.create_user(username="other-user", password="A-strong-password-123")
    own_session = DivinationSession.objects.create(
        user=user,
        fortune_set=fortune_set,
        question="我的帳號可以看見這筆嗎？",
        category="career",
        interaction_mode="click",
    )
    DivinationSession.objects.create(
        user=other_user,
        fortune_set=fortune_set,
        question="這筆不該被看見。",
        category="career",
        interaction_mode="click",
    )

    history = client.get("/api/v1/divinations/")
    items = history.json()["data"]["items"]
    assert [item["session_id"] for item in items] == [str(own_session.session_uuid)]
