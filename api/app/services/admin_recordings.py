import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
from storage3.exceptions import StorageApiError
from supabase import SupabaseException, create_client

from api.app.config import Settings
from api.app.schemas.admin import AdminRecordingPlayback
from api.app.schemas.candidates import StorageProvider
from api.app.services.recording_storage import (
    AzureStorageConfigurationError,
    AzureStorageOperationError,
    create_azure_read_url,
)


class RecordingPlaybackUnavailableError(RuntimeError):
    pass


async def get_admin_recording_playback(
    settings: Settings,
    recording_id: UUID,
) -> AdminRecordingPlayback | None:
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        recording = await connection.fetchrow(
            """
            select storage_provider, storage_container, storage_path
            from public.recordings
            where id = $1
            """,
            recording_id,
        )
    finally:
        await connection.close()

    if recording is None:
        return None

    provider = StorageProvider(recording["storage_provider"])
    try:
        if provider is StorageProvider.AZURE:
            url = await create_azure_read_url(settings, recording["storage_path"])
            ttl_seconds = settings.azure_read_sas_ttl_seconds
        else:
            if not settings.supabase_url or not settings.supabase_service_role_key:
                raise RecordingPlaybackUnavailableError(
                    "Supabase recording access is not configured"
                )
            storage = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key,
            )
            response = await asyncio.to_thread(
                storage.storage.from_(recording["storage_container"]).create_signed_url,
                recording["storage_path"],
                settings.recording_signed_url_ttl_seconds,
            )
            url = response.get("signedURL") or response.get("signedUrl")
            if not url:
                raise RecordingPlaybackUnavailableError(
                    "Supabase did not return a recording access URL"
                )
            ttl_seconds = settings.recording_signed_url_ttl_seconds
    except RecordingPlaybackUnavailableError:
        raise
    except (
        AzureStorageConfigurationError,
        AzureStorageOperationError,
        StorageApiError,
        SupabaseException,
        ValueError,
    ) as exc:
        raise RecordingPlaybackUnavailableError(
            "Recording access could not be prepared"
        ) from exc

    return AdminRecordingPlayback(
        url=str(url),
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
    )
