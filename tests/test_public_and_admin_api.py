import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.divinations.models import DivinationSession
from apps.fortunes.models import Fortune, FortuneSet


@pytest.mark.django_db
def test_fortune_detail_api_gets_public_active_fortune():
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    fortune = Fortune.objects.create(fortune_set=fortune_set, number=12, poem="籤詩")

    response = APIClient().get(f"/api/v1/fortune-sets/{fortune_set.code}/fortunes/{fortune.number}/")

    assert response.status_code == 200
    assert response.data["data"]["number"] == 12
    assert response.data["data"]["poem"] == "籤詩"


def test_non_api_routes_are_not_served():
    response = APIClient().get("/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_divination_accepts_categories_only():
    response = APIClient().post(
        "/api/v1/divinations/",
        {"question": "工作是否順利？", "categories": ["career"], "interaction_mode": "click"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["categories"] == ["career"]
    assert "category" not in response.data["data"]

    response = APIClient().post(
        "/api/v1/divinations/",
        {"question": "工作是否順利？", "category": "career", "interaction_mode": "click"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_usage_stats_requires_admin():
    response = APIClient().get("/api/v1/admin/usage-stats/")

    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_usage_stats_returns_session_counts():
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    admin = User.objects.create_superuser("admin", "admin@example.com", "pass")
    DivinationSession.objects.create(
        fortune_set=fortune_set,
        question="工作？",
        category="career",
        interaction_mode="click",
        status="completed",
    )
    client = APIClient()
    client.force_authenticate(admin)

    response = client.get("/api/v1/admin/usage-stats/")

    assert response.status_code == 200
    assert response.data["data"]["total_sessions"] == 1
    assert response.data["data"]["completed_sessions"] == 1
    assert response.data["data"]["by_category"] == [{"category": "career", "count": 1}]


@pytest.mark.django_db
def test_admin_can_import_and_update_fortunes():
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    admin = User.objects.create_superuser("admin", "admin@example.com", "pass")
    client = APIClient()
    client.force_authenticate(admin)

    response = client.post(
        f"/api/v1/admin/fortune-sets/{fortune_set.code}/fortunes/import/",
        {"items": [{"number": 1, "poem": "新籤詩", "title": "第一籤"}]},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"] == {"imported": 1}
    assert Fortune.objects.get(fortune_set=fortune_set, number=1).poem == "新籤詩"


@pytest.mark.django_db
def test_fortune_import_requires_admin():
    response = APIClient().post(
        "/api/v1/admin/fortune-sets/SIXTY_JIAZI/fortunes/import/",
        {"items": [{"number": 1, "poem": "籤詩"}]},
        format="json",
    )

    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_full_flow_through_http_endpoints_including_chat(monkeypatch):
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    Fortune.objects.create(fortune_set=fortune_set, number=15, poem="籤詩")
    client = APIClient()

    create_response = client.post(
        "/api/v1/divinations/",
        {"question": "工作是否順利？", "categories": ["career"], "interaction_mode": "click"},
        format="json",
    )
    session_id = create_response.data["data"]["session_id"]

    client.post(f"/api/v1/divinations/{session_id}/prayer-complete/")
    client.post(f"/api/v1/divinations/{session_id}/draw/")

    sides = iter(["flat", "round"])
    monkeypatch.setattr("apps.divinations.services.random.choice", lambda choices: next(sides))
    cast_response = client.post(f"/api/v1/divinations/{session_id}/blocks/")
    assert cast_response.data["data"]["result"] == "sheng"

    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: "這支籤代表工作運穩定")
    interpret_response = client.post(f"/api/v1/divinations/{session_id}/interpret/")
    assert interpret_response.status_code == 200
    assert interpret_response.data["data"]["status"] == "completed"

    monkeypatch.setattr("apps.ai_service.services._chat", lambda messages: "可以先準備好履歷")
    chat_response = client.post(f"/api/v1/divinations/{session_id}/chat/", {"message": "我該做什麼準備？"}, format="json")

    assert chat_response.status_code == 200
    assert chat_response.data["data"]["reply"] == "可以先準備好履歷"
    assert isinstance(chat_response.data["data"]["messages"], list)
    assert chat_response.data["data"]["messages"][-1]["content"] == "可以先準備好履歷"

    # GET /chat/ requires an authenticated owner (STORY-003); this session was
    # created anonymously, so even its own creator can't GET it back without
    # logging in. See tests/test_story_003_chat_ownership.py for the
    # authenticated-owner/non-owner coverage of this endpoint.
    get_response = client.get(f"/api/v1/divinations/{session_id}/chat/")
    assert get_response.status_code == 401
