from fastapi.testclient import TestClient

from api.app.main import app


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_me_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get("/api/me")

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Missing access token"
