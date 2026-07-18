from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.app.auth.dependencies import get_current_user
from api.app.config import Settings
from api.app.main import app
from api.app.schemas.auth import CurrentUser, UserRole
from api.app.services.dependency_health import check_recording_storage


def test_dependency_health_requires_admin() -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="00000000-0000-0000-0000-000000000001",
        role=UserRole.PANEL,
        panel_id="00000000-0000-0000-0000-000000000002",
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/health/dependencies")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_dependency_health_reports_status() -> None:
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id="00000000-0000-0000-0000-000000000001",
        role=UserRole.ADMIN,
    )
    dependencies = [
        {"name": "database", "ok": True, "latency_ms": 5, "detail": "available"},
        {"name": "deepgram", "ok": True, "latency_ms": 10, "detail": "authenticated"},
    ]
    try:
        with patch(
            "api.app.routers.dependencies.check_runtime_dependencies",
            new=AsyncMock(return_value=dependencies),
        ), TestClient(app) as client:
            response = client.get("/api/health/dependencies")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_azure_dependency_health_checks_user_delegation_access() -> None:
    settings = Settings(
        recording_storage_provider="azure",
        azure_storage_account_name="intervuetest",
        azure_storage_connection_string="",
    )
    with patch(
        "api.app.services.dependency_health.verify_azure_container",
        new=AsyncMock(),
    ) as verify_mock:
        result = await check_recording_storage(settings)

    assert result.ok is True
    assert result.detail == "Azure container and user delegation authenticated"
    verify_mock.assert_awaited_once_with(settings)
