from uuid import UUID

import pytest

from api.app.config import Settings
from api.app.schemas.candidates import CandidateCreate
from api.app.services.candidates import (
    InvalidRecordingPathError,
    _validate_recording_path,
    create_candidate,
)

PANEL_ID = UUID("00000000-0000-0000-0000-000000000002")


def test_recording_path_must_belong_to_panel() -> None:
    with pytest.raises(InvalidRecordingPathError, match="does not belong"):
        _validate_recording_path(
            "00000000-0000-0000-0000-000000000099/"
            "00000000-0000-0000-0000-000000000004/interview.mp3",
            PANEL_ID,
        )


def test_recording_path_accepts_server_shape() -> None:
    _validate_recording_path(
        f"{PANEL_ID}/00000000-0000-0000-0000-000000000004/interview.webm",
        PANEL_ID,
    )


@pytest.mark.asyncio
async def test_candidate_rejects_inactive_storage_provider() -> None:
    candidate = CandidateCreate.model_validate(
        {
            "full_name": "Ada Lovelace",
            "external_id": "ENR-101",
            "category": "full_stack_engineer",
            "recording": {
                "storage_provider": "supabase",
                "storage_container": "recordings",
                "storage_path": (
                    f"{PANEL_ID}/00000000-0000-0000-0000-000000000004/interview.mp3"
                ),
                "original_filename": "interview.mp3",
                "size_bytes": 1024,
                "mime_type": "audio/mpeg",
            },
        }
    )

    with pytest.raises(InvalidRecordingPathError, match="active storage"):
        await create_candidate(
            Settings(recording_storage_provider="azure"),
            PANEL_ID,
            UUID("00000000-0000-0000-0000-000000000001"),
            candidate,
        )
