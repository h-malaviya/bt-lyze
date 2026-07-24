from typing import Annotated
from uuid import UUID

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.app.auth.dependencies import CurrentUserDependency
from api.app.config import Settings, get_settings
from api.app.schemas.admin import (
    AdminCandidateDetail,
    AdminCandidateListResponse,
    AdminRecordingPlayback,
    Recommendation,
    ScoreBand,
)
from api.app.schemas.auth import UserRole
from api.app.schemas.candidates import JobStage, Verdict
from api.app.services.admin_candidates import get_admin_candidate, list_admin_candidates
from api.app.services.admin_recordings import (
    RecordingPlaybackUnavailableError,
    get_admin_recording_playback,
)

router = APIRouter(prefix="/admin", tags=["admin"])
logger = structlog.get_logger()


def _require_admin(current_user: CurrentUserDependency) -> None:
    if current_user.role is not UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An administrator account is required",
        )


@router.get("/candidates", response_model=AdminCandidateListResponse)
async def list_admin_candidates_route(
    current_user: CurrentUserDependency,
    settings: Annotated[Settings, Depends(get_settings)],
    search: Annotated[str | None, Query(max_length=200)] = None,
    panel_id: Annotated[UUID | None, Query()] = None,
    verdict: Annotated[Verdict | None, Query()] = None,
    stage: Annotated[JobStage | None, Query()] = None,
    recommendation: Annotated[Recommendation | None, Query()] = None,
    score_band: Annotated[ScoreBand | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminCandidateListResponse:
    _require_admin(current_user)
    try:
        response = await list_admin_candidates(
            settings,
            search,
            panel_id,
            verdict,
            stage,
            recommendation,
            score_band,
            limit,
            offset,
        )
        logger.info(
            "admin_candidates_loaded",
            admin_user_id=str(current_user.id),
            returned=len(response.items),
            total=response.total,
        )
        return response
    except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
        logger.exception("admin_candidates_load_failed", admin_user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Candidate intelligence could not be loaded. Please try again.",
        ) from exc


@router.get("/candidates/{candidate_id}", response_model=AdminCandidateDetail)
async def get_admin_candidate_route(
    candidate_id: UUID,
    current_user: CurrentUserDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminCandidateDetail:
    _require_admin(current_user)
    try:
        candidate = await get_admin_candidate(settings, candidate_id)
    except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
        logger.exception(
            "admin_candidate_detail_load_failed",
            admin_user_id=str(current_user.id),
            candidate_id=str(candidate_id),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Candidate analysis could not be loaded. Please try again.",
        ) from exc
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    logger.info(
        "admin_candidate_detail_loaded",
        admin_user_id=str(current_user.id),
        candidate_id=str(candidate_id),
    )
    return candidate


@router.get(
    "/recordings/{recording_id}/playback",
    response_model=AdminRecordingPlayback,
)
async def get_admin_recording_playback_route(
    recording_id: UUID,
    current_user: CurrentUserDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminRecordingPlayback:
    _require_admin(current_user)
    try:
        playback = await get_admin_recording_playback(settings, recording_id)
    except (
        asyncpg.PostgresError,
        OSError,
        TimeoutError,
        RecordingPlaybackUnavailableError,
    ) as exc:
        logger.exception(
            "admin_recording_playback_failed",
            admin_user_id=str(current_user.id),
            recording_id=str(recording_id),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recording playback could not be prepared. Please try again.",
        ) from exc
    if playback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording not found")
    logger.info(
        "admin_recording_playback_loaded",
        admin_user_id=str(current_user.id),
        recording_id=str(recording_id),
    )
    return playback
