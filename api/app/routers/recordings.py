from typing import Annotated

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from api.app.auth.dependencies import CurrentUserDependency
from api.app.config import Settings, get_settings
from api.app.schemas.auth import UserRole
from api.app.schemas.candidates import StorageProvider
from api.app.schemas.recordings import (
    RecordingUploadCleanupRequest,
    RecordingUploadGrant,
    RecordingUploadRequest,
)
from api.app.services.recording_storage import (
    AzureStorageConfigurationError,
    AzureStorageOperationError,
    create_azure_upload_grant,
    create_recording_path,
    delete_azure_blob,
    validate_recording_path,
)

router = APIRouter(prefix="/recordings", tags=["recordings"])
logger = structlog.get_logger()


def _require_panel(current_user: CurrentUserDependency):
    if current_user.role is not UserRole.PANEL or current_user.panel_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A panel account with a panel assignment is required",
        )
    return current_user.panel_id


@router.post("/upload-url", response_model=RecordingUploadGrant)
async def create_recording_upload_url(
    upload: RecordingUploadRequest,
    current_user: CurrentUserDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RecordingUploadGrant:
    panel_id = _require_panel(current_user)
    if upload.size_bytes > settings.max_recording_size_bytes:
        maximum_mb = settings.max_recording_size_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"The recording must be {maximum_mb} MB or smaller",
        )

    storage_path = create_recording_path(
        panel_id,
        upload.candidate_name,
        upload.original_filename,
    )
    if settings.recording_storage_provider == StorageProvider.SUPABASE:
        return RecordingUploadGrant(
            storage_provider=StorageProvider.SUPABASE,
            storage_container=settings.recordings_bucket,
            storage_path=storage_path,
        )

    try:
        grant = await create_azure_upload_grant(settings, storage_path)
    except AzureStorageConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AzureStorageOperationError as exc:
        logger.exception("azure_upload_url_failed", panel_id=str(panel_id))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure could not prepare the recording upload. Please try again.",
        ) from exc

    logger.info(
        "azure_upload_url_created",
        panel_id=str(panel_id),
        storage_path=storage_path,
    )
    return RecordingUploadGrant(
        storage_provider=StorageProvider.AZURE,
        storage_container=settings.azure_storage_container,
        storage_path=storage_path,
        upload_url=grant.upload_url,
        upload_headers={"x-ms-blob-type": "BlockBlob"},
        expires_at=grant.expires_at,
    )


@router.delete("/upload", status_code=status.HTTP_204_NO_CONTENT)
async def cleanup_recording_upload(
    cleanup: RecordingUploadCleanupRequest,
    current_user: CurrentUserDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    panel_id = _require_panel(current_user)
    try:
        validate_recording_path(cleanup.storage_path, panel_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if cleanup.storage_provider is not StorageProvider.AZURE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only Azure uploads are cleaned through this endpoint",
        )
    if cleanup.storage_container != settings.azure_storage_container:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Recording container is invalid",
        )
    try:
        connection = await asyncpg.connect(settings.database_url, timeout=15)
        try:
            is_registered = await connection.fetchval(
                """
                select exists(
                  select 1 from public.recordings
                  where storage_provider = 'azure'
                    and storage_container = $1
                    and storage_path = $2
                )
                """,
                cleanup.storage_container,
                cleanup.storage_path,
            )
        finally:
            await connection.close()
    except (asyncpg.PostgresError, OSError, TimeoutError) as exc:
        logger.exception("azure_upload_cleanup_check_failed", panel_id=str(panel_id))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recording cleanup could not be verified. Please try again.",
        ) from exc
    if is_registered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A submitted candidate recording cannot be removed as an abandoned upload",
        )
    try:
        await delete_azure_blob(settings, cleanup.storage_path)
    except (AzureStorageConfigurationError, AzureStorageOperationError) as exc:
        logger.exception(
            "azure_upload_cleanup_failed",
            panel_id=str(panel_id),
            storage_path=cleanup.storage_path,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure recording cleanup failed. Please try again.",
        ) from exc
    logger.info(
        "azure_upload_cleaned",
        panel_id=str(panel_id),
        storage_path=cleanup.storage_path,
    )
