from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.app.auth.dependencies import get_current_user
from api.app.main import app
from api.app.schemas.admin import AdminCandidateDetail, AdminCandidateListResponse
from api.app.schemas.auth import CurrentUser, UserRole

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
                "overall_score": 8.5,
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
            "overall_score": 8.5,
            "scores": {
                key: {"score": 8.5, "rationale": "Strong evidence"}
                for key in ["technical", "communication", "problem_solving", "culture"]
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
                "/api/admin/candidates?search=Love&stage=completed"
                "&recommendation=selected&score_band=8_to_10"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["metrics"]["ready"] == 1
    assert response.json()["items"][0]["recommendation"] == "selected"
    assert list_mock.await_args.args[1] == "Love"
    assert list_mock.await_args.args[3].value == "completed"
    assert list_mock.await_args.args[5] == "8_to_10"


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
