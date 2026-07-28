from rest_framework.test import APIClient


def test_health_check_is_public_and_ok():
    response = APIClient().get("/api/v1/health/")

    assert response.status_code == 200
    assert response.data["data"] == {"status": "ok"}
