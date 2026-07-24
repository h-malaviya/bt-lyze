from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.app.auth.dependencies import get_current_user
from api.app.config import Settings
from api.app.main import app
from api.app.schemas.admin import (
    AdminCandidateDetail,
    AdminCandidateListResponse,
    AdminRecordingPlayback,
)
from api.app.schemas.auth import CurrentUser, UserRole
from api.app.services.admin_recordings import get_admin_recording_playback

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
PANEL_ID = "00000000-0000-0000-0000-000000000002"
CANDIDATE_ID = "00000000-0000-0000-0000-000000000003"
RECORDING_ID = "00000000-0000-0000-0000-000000000004"
CREATED_AT = "2026-07-17T10:00:00Z"

LIST_RESPONSE = AdminCandidateListResponse.model_validate(
    {
        "items": [
            {
                "id": CANDIDATE_ID,
                "external_id": "C-101",
                "full_name": "Ada Lovelace",
                "category": "ai_ml",
                "panel_id": PANEL_ID,
                "panel_name": "Panel 1",
                "verdict": "selected",
                "recording_id": RECORDING_ID,
                "stage": "completed",
                "overall_score": 4,
                "recommendation": "selected",
                "created_at": CREATED_AT,
                "updated_at": CREATED_AT,
            }
        ],
        "total": 1,
        "metrics": {"candidates": 1, "ready": 1, "in_progress": 0, "needs_attention": 0},
        "panels": [{"id": PANEL_ID, "name": "Panel 1"}],
    }
)

DETAIL_RESPONSE = AdminCandidateDetail.model_validate(
    {
        "id": CANDIDATE_ID,
        "external_id": "C-101",
        "full_name": "Ada Lovelace",
        "category": "ai_ml",
        "panel_id": PANEL_ID,
        "panel_name": "Panel 1",
        "verdict": "selected",
        "notes": "Strong reasoning",
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "recording": {
            "id": RECORDING_ID,
            "storage_provider": "azure",
            "storage_container": "recordings",
            "original_filename": "interview.m4a",
            "duration_sec": 600,
            "size_bytes": 1024,
            "mime_type": "audio/mp4",
            "stage": "completed",
            "attempt_count": 1,
            "last_error": None,
            "created_at": CREATED_AT,
            "updated_at": CREATED_AT,
        },
        "transcript": {
            "text": "Speaker 0: Question\nSpeaker 1: Answer",
            "language": "en",
            "created_at": CREATED_AT,
        },
        "evaluation": {
            "version": 1,
            "overall_score": 4,
            "scores": {
                key: {"score": 4, "rationale": "Strong evidence"}
                for key in [
                    "project_deep_dive",
                    "fundamentals",
                    "live_problem",
                    "learning_ability_and_trends",
                    "candidate_questions",
                ]
            },
            "summary": "Strong candidate",
            "strengths": ["Clear reasoning"],
            "concerns": ["Limited monitoring detail"],
            "recommendation": "selected",
            "prompt_version": "interview-v1",
            "model": "claude-sonnet-4-6",
            "token_usage": {
                "input_tokens": 25,
                "output_tokens": 80,
                "cache_creation_input_tokens": 1_500,
                "cache_read_input_tokens": 0,
                "total_input_tokens": 1_525,
                "cache_hit": False,
                "total_cost_usd": 0.01,
            },
            "created_at": CREATED_AT,
        },
        "events": [
            {
                "id": 1,
                "stage": "completed",
                "status": "succeeded",
                "detail": "Evaluation saved",
                "created_at": CREATED_AT,
            }
        ],
    }
)


def admin_user() -> CurrentUser:
    return CurrentUser(id=ADMIN_ID, role=UserRole.ADMIN)


def panel_user() -> CurrentUser:
    return CurrentUser(id=ADMIN_ID, role=UserRole.PANEL, panel_id=PANEL_ID)


def test_admin_can_list_candidates_with_filters_and_metrics() -> None:
    app.dependency_overrides[get_current_user] = admin_user
    try:
        with patch(
            "api.app.routers.admin.list_admin_candidates",
            new=AsyncMock(return_value=LIST_RESPONSE),
        ) as list_mock, TestClient(app) as client:
            response = client.get(
                "/api/admin/candidates?search=Love&verdict=selected&stage=completed"
                "&recommendation=selected&score_band=4_to_5"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["metrics"]["ready"] == 1
    assert response.json()["items"][0]["recommendation"] == "selected"
    assert list_mock.await_args.args[1] == "Love"
    assert list_mock.await_args.args[3].value == "selected"
    assert list_mock.await_args.args[4].value == "completed"
    assert list_mock.await_args.args[6] == "4_to_5"


def test_admin_can_load_complete_candidate_analysis() -> None:
    app.dependency_overrides[get_current_user] = admin_user
    try:
        with patch(
            "api.app.routers.admin.get_admin_candidate",
            new=AsyncMock(return_value=DETAIL_RESPONSE),
        ), TestClient(app) as client:
            response = client.get(f"/api/admin/candidates/{CANDIDATE_ID}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["evaluation"]["summary"] == "Strong candidate"
    assert response.json()["evaluation"]["token_usage"]["output_tokens"] == 80
    assert "Speaker 1" in response.json()["transcript"]["text"]
    assert response.json()["events"][0]["status"] == "succeeded"


def test_admin_can_load_recording_playback_url() -> None:
    app.dependency_overrides[get_current_user] = admin_user
    playback = AdminRecordingPlayback.model_validate(
        {
            "url": "https://storage.example/interview.m4a?signed",
            "expires_at": "2026-07-17T12:00:00Z",
        }
    )
    try:
        with patch(
            "api.app.routers.admin.get_admin_recording_playback",
            new=AsyncMock(return_value=playback),
        ), TestClient(app) as client:
            response = client.get(f"/api/admin/recordings/{RECORDING_ID}/playback")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["url"].endswith("?signed")


def test_panel_cannot_load_recording_playback_url() -> None:
    app.dependency_overrides[get_current_user] = panel_user
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/admin/recordings/{RECORDING_ID}/playback")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_supabase_playback_uses_recorded_bucket_and_path() -> None:
    connection = AsyncMock()
    connection.fetchrow.return_value = {
        "storage_provider": "supabase",
        "storage_container": "recordings",
        "storage_path": f"{PANEL_ID}/upload/interview.m4a",
    }
    bucket = MagicMock()
    bucket.create_signed_url.return_value = {
        "signedURL": "https://storage.example/interview.m4a?signed"
    }
    storage = MagicMock()
    storage.storage.from_.return_value = bucket
    settings = Settings(
        database_url="postgresql://example",
        supabase_url="https://project.supabase.co",
        supabase_service_role_key="service-role-key",
    )

    with patch(
        "api.app.services.admin_recordings.asyncpg.connect",
        new=AsyncMock(return_value=connection),
    ), patch(
        "api.app.services.admin_recordings.create_client",
        return_value=storage,
    ):
        playback = await get_admin_recording_playback(settings, RECORDING_ID)

    assert playback is not None
    assert playback.url.endswith("?signed")
    storage.storage.from_.assert_called_once_with("recordings")
    bucket.create_signed_url.assert_called_once_with(
        f"{PANEL_ID}/upload/interview.m4a",
        settings.recording_signed_url_ttl_seconds,
    )


def test_panel_cannot_access_admin_candidates() -> None:
    app.dependency_overrides[get_current_user] = panel_user
    try:
        with TestClient(app) as client:
            response = client.get("/api/admin/candidates")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "An administrator account is required"


def test_missing_admin_candidate_returns_not_found() -> None:
    app.dependency_overrides[get_current_user] = admin_user
    try:
        with patch(
            "api.app.routers.admin.get_admin_candidate",
            new=AsyncMock(return_value=None),
        ), TestClient(app) as client:
            response = client.get(f"/api/admin/candidates/{CANDIDATE_ID}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
