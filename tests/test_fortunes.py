import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.fortunes.models import Fortune, FortuneSet


@pytest.mark.django_db
def test_fortune_set_list_only_returns_public_active_sets():
    FortuneSet.objects.create(code="PRIVATE_SET", name="未公開籤系", is_active=True, is_public=False)
    FortuneSet.objects.create(code="INACTIVE_SET", name="停用籤系", is_active=False, is_public=True)

    response = APIClient().get("/api/v1/fortune-sets/")

    codes = [item["code"] for item in response.data["data"]["items"]]
    assert response.status_code == 200
    assert "SIXTY_JIAZI" in codes
    assert "PRIVATE_SET" not in codes
    assert "INACTIVE_SET" not in codes


@pytest.mark.django_db
def test_fortune_detail_hides_inactive_fortune():
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    Fortune.objects.create(fortune_set=fortune_set, number=13, poem="停用籤詩", is_active=False)

    response = APIClient().get(f"/api/v1/fortune-sets/{fortune_set.code}/fortunes/13/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_bulk_import_rejects_whole_batch_when_one_item_is_invalid():
    fortune_set = FortuneSet.objects.get(code="SIXTY_JIAZI")
    admin = User.objects.create_superuser("admin2", "admin2@example.com", "pass")
    client = APIClient()
    client.force_authenticate(admin)

    response = client.post(
        f"/api/v1/admin/fortune-sets/{fortune_set.code}/fortunes/import/",
        {
            "items": [
                {"number": 20, "poem": "有效籤詩"},
                {"poem": "缺少籤號"},
            ]
        },
        format="json",
    )

    assert response.status_code == 400
    assert not Fortune.objects.filter(fortune_set=fortune_set, number=20).exists()
