from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from api.app.auth.dependencies import get_current_user
from api.app.main import app
from api.app.schemas.auth import CurrentUser, UserRole
from api.app.schemas.candidates import CandidateResponse

PANEL_ID = "00000000-0000-0000-0000-000000000002"
USER_ID = "00000000-0000-0000-0000-000000000001"
CANDIDATE = {
    "id": "00000000-0000-0000-0000-000000000003",
    "external_id": "C-101",
    "full_name": "Ada Lovelace",
    "category": "ai_ml",
    "panel_id": PANEL_ID,
    "panel_name": "Panel 1",
    "verdict": "selected",
    "notes": "Strong reasoning",
    "recording_id": "00000000-0000-0000-0000-000000000005",
    "stage": "queued",
    "overall_score": None,
    "created_at": "2026-07-17T10:00:00Z",
    "updated_at": "2026-07-17T10:00:00Z",
}
RECORDING = {
    "storage_path": f"{PANEL_ID}/00000000-0000-0000-0000-000000000004/interview.m4a",
    "original_filename": "interview.m4a",
    "size_bytes": 1024,
    "mime_type": "audio/mp4",
}


def panel_user(panel_id: str | None = PANEL_ID) -> CurrentUser:
    return CurrentUser(id=USER_ID, role=UserRole.PANEL, panel_id=panel_id)


def test_panel_can_create_candidate() -> None:
    app.dependency_overrides[get_current_user] = panel_user
    try:
        with patch(
            "api.app.routers.candidates.create_candidate",
            new=AsyncMock(return_value=(CandidateResponse.model_validate(CANDIDATE), 10)),
        ) as create_mock, patch(
            "api.app.routers.candidates.create_pool",
            new=AsyncMock(),
        ) as pool_mock, patch(
            "api.app.routers.candidates.dispatch_outbox_job",
            new=AsyncMock(),
        ) as dispatch_mock, TestClient(app) as client:
            pool_mock.return_value.aclose = AsyncMock()
            response = client.post(
                "/api/candidates",
                json={
                    "full_name": "  Ada   Lovelace ",
                    "external_id": "C-101",
                    "category": "ai_ml",
                    "verdict": "selected",
                    "notes": "Strong reasoning",
                    "recording": RECORDING,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["full_name"] == "Ada Lovelace"
    candidate_payload = create_mock.await_args.args[3]
    assert candidate_payload.full_name == "Ada Lovelace"
    assert candidate_payload.category.value == "ai_ml"
    assert candidate_payload.verdict.value == "selected"
    assert candidate_payload.recording.original_filename == "interview.m4a"
    dispatch_mock.assert_awaited_once()


def test_panel_without_assignment_cannot_create_candidate() -> None:
    app.dependency_overrides[get_current_user] = lambda: panel_user(None)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/candidates",
                json={
                    "full_name": "Ada Lovelace",
                    "external_id": "ENR-101",
                    "category": "ai_ml",
                    "recording": RECORDING,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "panel assignment" in response.json()["error"]["message"]


def test_panel_candidate_list_is_scoped_to_panel() -> None:
    app.dependency_overrides[get_current_user] = panel_user
    try:
        with patch(
            "api.app.routers.candidates.list_candidates",
            new=AsyncMock(return_value=[CANDIDATE]),
        ) as list_mock, TestClient(app) as client:
            response = client.get("/api/candidates?scope=mine")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert list_mock.await_args.args[1].hex == PANEL_ID.replace("-", "")


def test_candidate_name_is_required() -> None:
    app.dependency_overrides[get_current_user] = panel_user
    try:
        with TestClient(app) as client:
            response = client.post("/api/candidates", json={"full_name": "   "})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_candidate_id_and_category_are_required() -> None:
    app.dependency_overrides[get_current_user] = panel_user
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/candidates",
                json={"full_name": "Ada Lovelace", "recording": RECORDING},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    fields = {error["loc"][-1] for error in response.json()["detail"]}
    assert fields == {"external_id", "category"}
