from typing import Annotated, Literal

import asyncpg
import structlog
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.exceptions import RedisError

from api.app.auth.dependencies import CurrentUserDependency
from api.app.config import Settings, get_settings
from api.app.schemas.auth import UserRole
from api.app.schemas.candidates import (
    CandidateCreate,
    CandidateListResponse,
    CandidateResponse,
)
from api.app.services.candidates import (
    InvalidRecordingPathError,
    RecordingObjectNotFoundError,
    create_candidate,
    list_candidates,
)
from api.app.services.job_queue import dispatch_outbox_job

router = APIRouter(prefix="/candidates", tags=["candidates"])
logger = structlog.get_logger()


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate_route(
    candidate: CandidateCreate,
    current_user: CurrentUserDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CandidateResponse:
    if current_user.role is not UserRole.PANEL or current_user.panel_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A panel account with a panel assignment is required",
        )

    try:
        created_candidate, outbox_id = await create_candidate(
            settings,
            current_user.panel_id,
            current_user.id,
            candidate,
        )
        logger.info(
            "candidate_submission_saved",
            candidate_id=str(created_candidate.id),
            recording_id=str(created_candidate.recording_id),
            outbox_id=outbox_id,
        )
    except InvalidRecordingPathError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RecordingObjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
        logger.exception("candidate_create_failed", user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Candidate could not be saved. Please try again.",
        ) from exc

    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await dispatch_outbox_job(settings, redis, outbox_id)
        finally:
            await redis.aclose()
        logger.info(
            "candidate_queue_dispatched",
            candidate_id=str(created_candidate.id),
            recording_id=str(created_candidate.recording_id),
            outbox_id=outbox_id,
        )
    except (asyncpg.PostgresError, RedisError, OSError, TimeoutError):
        logger.warning(
            "candidate_queue_deferred",
            user_id=str(current_user.id),
            candidate_id=str(created_candidate.id),
            recording_id=str(created_candidate.recording_id),
            outbox_id=outbox_id,
        )
    return created_candidate


@router.get("", response_model=CandidateListResponse)
async def list_candidates_route(
    current_user: CurrentUserDependency,
    settings: Annotated[Settings, Depends(get_settings)],
    scope: Annotated[Literal["mine", "all"], Query()] = "mine",
) -> CandidateListResponse:
    if current_user.role is UserRole.PANEL:
        if current_user.panel_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This panel account has no panel assignment",
            )
        panel_id = current_user.panel_id
    elif scope == "mine":
        panel_id = None
    else:
        panel_id = None

    try:
        candidates = await list_candidates(settings, panel_id)
        return CandidateListResponse(items=list(candidates), total=len(candidates))
    except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
        logger.exception("candidate_list_failed", user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Candidates could not be loaded. Please refresh and try again.",
        ) from exc
