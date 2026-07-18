import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg

from api.app.config import Settings
from api.app.schemas.admin import (
    AdminCandidateDetail,
    AdminCandidateItem,
    AdminCandidateListResponse,
    AdminEvaluationDetail,
    AdminJobEvent,
    AdminMetrics,
    AdminRecordingDetail,
    AdminTranscriptDetail,
    PanelOption,
    Recommendation,
    ScoreBand,
)
from api.app.schemas.candidates import JobStage

_LATEST_RECORDINGS = """
left join lateral (
  select recordings.*
  from public.recordings
  where recordings.candidate_id = candidates.id
  order by recordings.created_at desc
  limit 1
) as latest_recording on true
left join public.evaluations as current_evaluation
  on current_evaluation.recording_id = latest_recording.id
 and current_evaluation.is_current
"""

_FILTERS = """
where (
    $1::text is null
    or candidates.search_tsv @@ websearch_to_tsquery('english', $1)
    or strpos(
      lower(concat_ws(' ', candidates.full_name, candidates.external_id, candidates.notes)),
      lower($1)
    ) > 0
    or strpos(lower(candidates.id::text), lower($1)) > 0
  )
  and ($2::uuid is null or candidates.panel_id = $2)
  and ($3::public.job_stage is null or latest_recording.stage = $3)
  and ($4::text is null or current_evaluation.recommendation = $4)
  and (
    $5::text is null
    or ($5 = '4_to_5' and current_evaluation.overall_score >= 4)
    or ($5 = '3' and current_evaluation.overall_score = 3)
    or ($5 = '1_to_2' and current_evaluation.overall_score between 1 and 2)
    or ($5 = 'unscored' and current_evaluation.overall_score is null)
  )
"""


def _float_or_none(value: Any) -> float | None:
    return float(value) if value is not None else None


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return value if isinstance(value, dict) else {}


async def list_admin_candidates(
    settings: Settings,
    search: str | None,
    panel_id: UUID | None,
    stage: JobStage | None,
    recommendation: Recommendation | None,
    score_band: ScoreBand | None,
    limit: int,
    offset: int,
) -> AdminCandidateListResponse:
    filters = (
        search.strip() if search and search.strip() else None,
        panel_id,
        stage.value if stage else None,
        recommendation,
        score_band,
    )
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        records = await connection.fetch(
            """
            select candidates.id,
                   candidates.external_id,
                   candidates.full_name,
                   candidates.category,
                   candidates.panel_id,
                   panels.name as panel_name,
                   candidates.verdict,
                   latest_recording.id as recording_id,
                   latest_recording.stage,
                   current_evaluation.overall_score,
                   current_evaluation.recommendation,
                   candidates.created_at,
                   candidates.updated_at
            from public.candidates
            join public.panels on panels.id = candidates.panel_id
            """
            + _LATEST_RECORDINGS
            + _FILTERS
            + " order by candidates.created_at desc limit $6 offset $7",
            *filters,
            limit,
            offset,
        )
        total = await connection.fetchval(
            "select count(*) from public.candidates "
            + _LATEST_RECORDINGS
            + _FILTERS,
            *filters,
        )
        metric_record = await connection.fetchrow(
            """
            select count(*) as candidates,
                   count(*) filter (where latest_recording.stage = 'completed') as ready,
                   count(*) filter (
                     where latest_recording.stage in (
                       'uploaded', 'queued', 'transcribing', 'transcribed', 'analyzing'
                     )
                   ) as in_progress,
                   count(*) filter (
                     where latest_recording.stage = 'failed' or latest_recording.id is null
                   ) as needs_attention
            from public.candidates
            """
            + _LATEST_RECORDINGS
        )
        panel_records = await connection.fetch(
            "select id, name from public.panels where is_active order by name"
        )
    finally:
        await connection.close()

    items = []
    for record in records:
        values = dict(record)
        values["overall_score"] = _float_or_none(values["overall_score"])
        items.append(AdminCandidateItem.model_validate(values))
    metrics = AdminMetrics.model_validate(dict(metric_record))
    panels = [PanelOption.model_validate(dict(record)) for record in panel_records]
    return AdminCandidateListResponse(items=items, total=total, metrics=metrics, panels=panels)


async def get_admin_candidate(
    settings: Settings,
    candidate_id: UUID,
) -> AdminCandidateDetail | None:
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        record = await connection.fetchrow(
            """
            select candidates.id,
                   candidates.external_id,
                   candidates.full_name,
                   candidates.category,
                   candidates.panel_id,
                   panels.name as panel_name,
                   candidates.verdict,
                   candidates.notes,
                   candidates.created_at,
                   candidates.updated_at,
                   latest_recording.id as recording_id,
                   latest_recording.storage_provider,
                   latest_recording.storage_container,
                   latest_recording.original_filename,
                   latest_recording.duration_sec,
                   latest_recording.size_bytes,
                   latest_recording.mime_type,
                   latest_recording.stage,
                   latest_recording.attempt_count,
                   latest_recording.last_error,
                   latest_recording.created_at as recording_created_at,
                   latest_recording.updated_at as recording_updated_at,
                   transcripts.text as transcript_text,
                   transcripts.language as transcript_language,
                   transcripts.created_at as transcript_created_at,
                   current_evaluation.version,
                   current_evaluation.overall_score,
                   current_evaluation.scores,
                   current_evaluation.summary,
                   current_evaluation.strengths,
                   current_evaluation.concerns,
                   current_evaluation.recommendation,
                   current_evaluation.prompt_version,
                   current_evaluation.model,
                   current_evaluation.token_usage,
                   current_evaluation.created_at as evaluation_created_at
            from public.candidates
            join public.panels on panels.id = candidates.panel_id
            """
            + _LATEST_RECORDINGS
            + " left join public.transcripts on transcripts.recording_id = latest_recording.id"
            + " where candidates.id = $1",
            candidate_id,
        )
        if record is None:
            return None

        events: Sequence[asyncpg.Record] = []
        if record["recording_id"] is not None:
            events = await connection.fetch(
                """
                select id, stage, status, detail, created_at
                from public.job_events
                where recording_id = $1
                order by created_at
                """,
                record["recording_id"],
            )
    finally:
        await connection.close()

    recording = None
    transcript = None
    evaluation = None
    if record["recording_id"] is not None:
        recording = AdminRecordingDetail.model_validate(
            {
                "id": record["recording_id"],
                "storage_provider": record["storage_provider"],
                "storage_container": record["storage_container"],
                "original_filename": record["original_filename"],
                "duration_sec": record["duration_sec"],
                "size_bytes": record["size_bytes"],
                "mime_type": record["mime_type"],
                "stage": record["stage"],
                "attempt_count": record["attempt_count"],
                "last_error": record["last_error"],
                "created_at": record["recording_created_at"],
                "updated_at": record["recording_updated_at"],
            }
        )
    if record["transcript_created_at"] is not None:
        transcript = AdminTranscriptDetail(
            text=record["transcript_text"],
            language=record["transcript_language"],
            created_at=record["transcript_created_at"],
        )
    if record["evaluation_created_at"] is not None:
        evaluation = AdminEvaluationDetail.model_validate(
            {
                "version": record["version"],
                "overall_score": _float_or_none(record["overall_score"]),
                "scores": _json_object(record["scores"]),
                "summary": record["summary"],
                "strengths": record["strengths"],
                "concerns": record["concerns"],
                "recommendation": record["recommendation"],
                "prompt_version": record["prompt_version"],
                "model": record["model"],
                "token_usage": (
                    _json_object(record["token_usage"])
                    if record["token_usage"] is not None
                    else None
                ),
                "created_at": record["evaluation_created_at"],
            }
        )
    return AdminCandidateDetail.model_validate(
        {
            "id": record["id"],
            "external_id": record["external_id"],
            "full_name": record["full_name"],
            "category": record["category"],
            "panel_id": record["panel_id"],
            "panel_name": record["panel_name"],
            "verdict": record["verdict"],
            "notes": record["notes"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "recording": recording,
            "transcript": transcript,
            "evaluation": evaluation,
            "events": [AdminJobEvent.model_validate(dict(event)) for event in events],
        }
    )
