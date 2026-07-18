from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.app.auth.dependencies import get_current_user
from api.app.config import Settings, get_settings
from api.app.main import app
from api.app.schemas.auth import CurrentUser, UserRole
from api.app.services.recording_storage import (
    AzureUploadGrant,
    candidate_recording_filename,
    create_azure_upload_grant,
)

PANEL_ID = "00000000-0000-0000-0000-000000000002"
USER_ID = "00000000-0000-0000-0000-000000000001"


def panel_user() -> CurrentUser:
    return CurrentUser(id=USER_ID, role=UserRole.PANEL, panel_id=PANEL_ID)


def upload_payload() -> dict[str, object]:
    return {
        "candidate_name": "Ada Lovelace",
        "original_filename": "Interview Final.M4A",
        "size_bytes": 1024,
        "mime_type": "audio/mp4",
    }


def test_candidate_recording_filename_preserves_extension() -> None:
    assert candidate_recording_filename(" José  Patel ", "Final.WEBM") == "jose-patel.webm"


def test_supabase_upload_grant_uses_authenticated_panel_path() -> None:
    app.dependency_overrides[get_current_user] = panel_user
    app.dependency_overrides[get_settings] = lambda: Settings(
        recording_storage_provider="supabase"
    )
    try:
        with TestClient(app) as client:
            response = client.post("/api/recordings/upload-url", json=upload_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["storage_provider"] == "supabase"
    assert payload["storage_container"] == "recordings"
    assert payload["storage_path"].startswith(f"{PANEL_ID}/")
    assert payload["storage_path"].endswith("/ada-lovelace.m4a")
    assert payload["upload_url"] is None


def test_azure_upload_grant_returns_short_lived_blob_url() -> None:
    app.dependency_overrides[get_current_user] = panel_user
    app.dependency_overrides[get_settings] = lambda: Settings(
        recording_storage_provider="azure",
        azure_storage_account_name="intervuetest",
    )
    grant = AzureUploadGrant(
        upload_url="https://intervuetest.blob.core.windows.net/recordings/blob?sas",
        expires_at=datetime(2026, 7, 17, 12, 15, tzinfo=UTC),
    )
    try:
        with patch(
            "api.app.routers.recordings.create_azure_upload_grant",
            new=AsyncMock(return_value=grant),
        ), TestClient(app) as client:
            response = client.post("/api/recordings/upload-url", json=upload_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["storage_provider"] == "azure"
    assert payload["upload_headers"] == {"x-ms-blob-type": "BlockBlob"}
    assert payload["upload_url"].endswith("?sas")


async def test_account_key_connection_string_creates_upload_sas() -> None:
    settings = Settings(
        azure_storage_account_name="intervuetest",
        azure_storage_container="recordings",
        azure_storage_connection_string=(
            "DefaultEndpointsProtocol=https;AccountName=intervuetest;"
            "AccountKey=a2V5;EndpointSuffix=core.windows.net"
        ),
    )

    grant = await create_azure_upload_grant(settings, "panel/recording/interview.wav")

    assert grant.upload_url.startswith(
        "https://intervuetest.blob.core.windows.net/recordings/"
    )
    assert "sp=cw" in grant.upload_url


def test_panel_cannot_cleanup_another_panels_upload() -> None:
    app.dependency_overrides[get_current_user] = panel_user
    try:
        with TestClient(app) as client:
            response = client.request(
                "DELETE",
                "/api/recordings/upload",
                json={
                    "storage_provider": "azure",
                    "storage_container": "recordings",
                    "storage_path": (
                        "00000000-0000-0000-0000-000000000099/"
                        "00000000-0000-0000-0000-000000000004/interview.m4a"
                    ),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_registered_azure_recording_cannot_be_cleaned_as_abandoned() -> None:
    app.dependency_overrides[get_current_user] = panel_user
    app.dependency_overrides[get_settings] = lambda: Settings(
        recording_storage_provider="azure",
        azure_storage_account_name="intervuetest",
        azure_storage_container="recordings",
    )
    connection = AsyncMock()
    connection.fetchval.return_value = True
    try:
        with patch(
            "api.app.routers.recordings.asyncpg.connect",
            new=AsyncMock(return_value=connection),
        ), patch(
            "api.app.routers.recordings.delete_azure_blob",
            new=AsyncMock(),
        ) as delete_mock, TestClient(app) as client:
            response = client.request(
                "DELETE",
                "/api/recordings/upload",
                json={
                    "storage_provider": "azure",
                    "storage_container": "recordings",
                    "storage_path": (
                        f"{PANEL_ID}/00000000-0000-0000-0000-000000000004/"
                        "ada-lovelace.m4a"
                    ),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    delete_mock.assert_not_awaited()
