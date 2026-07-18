from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg

from api.app.config import Settings
from api.app.schemas.candidates import CandidateCreate, CandidateResponse, StorageProvider
from api.app.services.recording_storage import (
    AzureBlobNotFoundError,
    AzureBlobSizeMismatchError,
    AzureStorageConfigurationError,
    AzureStorageOperationError,
    validate_recording_path,
    verify_azure_blob,
)


class RecordingObjectNotFoundError(RuntimeError):
    pass


class InvalidRecordingPathError(ValueError):
    pass

_CANDIDATE_SELECT = """
select
  candidates.id,
  candidates.external_id,
  candidates.full_name,
  candidates.category,
  candidates.panel_id,
  panels.name as panel_name,
  candidates.verdict,
  candidates.notes,
  latest_recording.id as recording_id,
  latest_recording.stage,
  current_evaluation.overall_score,
  candidates.created_at,
  candidates.updated_at
from public.candidates
join public.panels on panels.id = candidates.panel_id
left join lateral (
  select recordings.id, recordings.stage
  from public.recordings
  where recordings.candidate_id = candidates.id
  order by recordings.created_at desc
  limit 1
) as latest_recording on true
left join public.evaluations as current_evaluation
  on current_evaluation.recording_id = latest_recording.id
 and current_evaluation.is_current
"""


def _to_candidate(record: asyncpg.Record) -> CandidateResponse:
    values: dict[str, Any] = dict(record)
    if values["overall_score"] is not None:
        values["overall_score"] = float(values["overall_score"])
    return CandidateResponse.model_validate(values)


async def create_candidate(
    settings: Settings,
    panel_id: UUID,
    created_by: UUID,
    candidate: CandidateCreate,
) -> tuple[CandidateResponse, int]:
    _validate_recording_path(candidate.recording.storage_path, panel_id)
    if candidate.recording.size_bytes > settings.max_recording_size_bytes:
        maximum_mb = settings.max_recording_size_bytes // (1024 * 1024)
        raise InvalidRecordingPathError(f"Recording exceeds the {maximum_mb} MB upload limit")

    provider = candidate.recording.storage_provider
    if provider.value != settings.recording_storage_provider:
        raise InvalidRecordingPathError("Recording provider does not match the active storage")
    expected_container = (
        settings.azure_storage_container
        if provider is StorageProvider.AZURE
        else settings.recordings_bucket
    )
    storage_container = candidate.recording.storage_container or expected_container
    if storage_container != expected_container:
        raise InvalidRecordingPathError("Recording container is invalid")
    if provider is StorageProvider.AZURE:
        try:
            await verify_azure_blob(
                settings,
                candidate.recording.storage_path,
                candidate.recording.size_bytes,
            )
        except AzureBlobNotFoundError as exc:
            raise RecordingObjectNotFoundError(str(exc)) from exc
        except AzureBlobSizeMismatchError as exc:
            raise InvalidRecordingPathError(str(exc)) from exc
        except AzureStorageConfigurationError as exc:
            raise AzureStorageOperationError("Azure Blob Storage is not configured") from exc

    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        if provider is StorageProvider.SUPABASE:
            storage_object = await connection.fetchrow(
                """
                select metadata
                from storage.objects
                where bucket_id = $1 and name = $2
                """,
                storage_container,
                candidate.recording.storage_path,
            )
            if storage_object is None:
                raise RecordingObjectNotFoundError("Uploaded recording could not be found")

        async with connection.transaction():
            candidate_id = await connection.fetchval(
                """
                insert into public.candidates (
                  full_name,
                  external_id,
                  category,
                  panel_id,
                  verdict,
                  notes,
                  created_by
                ) values ($1, $2, $3, $4, $5, $6, $7)
                returning id
                """,
                candidate.full_name,
                candidate.external_id,
                candidate.category.value,
                panel_id,
                candidate.verdict.value,
                candidate.notes,
                created_by,
            )
            recording_id = await connection.fetchval(
                """
                insert into public.recordings (
                  candidate_id,
                  storage_provider,
                  storage_container,
                  storage_path,
                  original_filename,
                  size_bytes,
                  mime_type,
                  stage
                ) values ($1, $2, $3, $4, $5, $6, $7, 'queued')
                returning id
                """,
                candidate_id,
                provider.value,
                storage_container,
                candidate.recording.storage_path,
                candidate.recording.original_filename,
                candidate.recording.size_bytes,
                candidate.recording.mime_type,
            )
            await connection.execute(
                """
                insert into public.job_events (recording_id, stage, status, detail)
                values ($1, 'queued', 'succeeded', 'Recording uploaded and queued')
                """,
                recording_id,
            )
            outbox_id = await connection.fetchval(
                """
                insert into public.job_outbox (recording_id, job_name)
                values ($1, 'process_recording')
                returning id
                """,
                recording_id,
            )

        record = await connection.fetchrow(
            _CANDIDATE_SELECT + " where candidates.id = $1",
            candidate_id,
        )
        if record is None:
            raise RuntimeError("Created candidate could not be loaded")
        return _to_candidate(record), outbox_id
    finally:
        await connection.close()


def _validate_recording_path(storage_path: str, panel_id: UUID) -> None:
    try:
        validate_recording_path(storage_path, panel_id)
    except ValueError as exc:
        raise InvalidRecordingPathError(str(exc)) from exc


async def list_candidates(
    settings: Settings,
    panel_id: UUID | None,
) -> Sequence[CandidateResponse]:
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        if panel_id is None:
            records = await connection.fetch(
                _CANDIDATE_SELECT + " order by candidates.created_at desc limit 500"
            )
        else:
            records = await connection.fetch(
                _CANDIDATE_SELECT
                + " where candidates.panel_id = $1 order by candidates.created_at desc limit 500",
                panel_id,
            )
        return [_to_candidate(record) for record in records]
    finally:
        await connection.close()
