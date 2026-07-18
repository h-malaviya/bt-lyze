import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID

import asyncpg
import httpx
import structlog
from arq import Retry
from deepgram.core.api_error import ApiError
from supabase import Client

from api.app.config import Settings
from api.app.schemas.candidates import CandidateCategory, StorageProvider
from api.app.services.recording_storage import create_azure_read_url
from worker.integrations.claude_sdk import EvaluationResult
from worker.integrations.deepgram import DeepgramTranscriber
from worker.integrations.interview_flow_prompt import INTERVIEW_PROMPT_VERSION

logger = structlog.get_logger()
RETRY_DELAYS_SECONDS = (30, 120)
NORMALIZABLE_DEEPGRAM_STATUS_CODES = {400, 415, 422}


@dataclass(frozen=True)
class RecordingWork:
    recording_id: UUID
    storage_path: str
    original_filename: str
    transcript: str | None
    storage_provider: StorageProvider = StorageProvider.SUPABASE
    storage_container: str = "recordings"
    category: CandidateCategory | None = None


@dataclass(frozen=True)
class TranscriptPayload:
    text: str
    words: list[dict[str, Any]]
    language: str | None
    provider_meta: dict[str, Any]
    request_id: str | None


def extract_transcript(response: dict[str, Any]) -> TranscriptPayload:
    results = response.get("results") or {}
    channels = results.get("channels") or []
    alternatives = channels[0].get("alternatives") or [] if channels else []
    alternative = alternatives[0] if alternatives else {}
    utterances = results.get("utterances") or []
    diarized_lines = [
        f"Speaker {utterance.get('speaker', '?')}: {utterance.get('transcript', '').strip()}"
        for utterance in utterances
        if utterance.get("transcript", "").strip()
    ]
    text = "\n".join(diarized_lines) or str(alternative.get("transcript") or "").strip()
    if not text:
        raise ValueError("Deepgram returned an empty transcript")

    metadata = response.get("metadata") or {}
    language = channels[0].get("detected_language") if channels else None
    return TranscriptPayload(
        text=text,
        words=alternative.get("words") or [],
        language=language,
        provider_meta={"metadata": metadata, "utterances": utterances},
        request_id=metadata.get("request_id"),
    )


async def create_signed_recording_url(
    storage: Client,
    settings: Settings,
    work: RecordingWork,
) -> str:
    if work.storage_provider is StorageProvider.AZURE:
        return await create_azure_read_url(settings, work.storage_path)
    response = await asyncio.to_thread(
        storage.storage.from_(work.storage_container).create_signed_url,
        work.storage_path,
        settings.recording_signed_url_ttl_seconds,
    )
    signed_url = response.get("signedURL") or response.get("signedUrl")
    if not signed_url:
        raise RuntimeError("Supabase did not return a signed recording URL")
    return str(signed_url)


async def transcribe_with_fallback(
    transcriber: DeepgramTranscriber,
    audio_url: str,
    original_filename: str,
) -> dict[str, Any]:
    try:
        response = await transcriber.transcribe_url(audio_url)
        logger.info("deepgram_direct_transcription_succeeded")
        return response
    except ApiError as exc:
        if exc.status_code not in NORMALIZABLE_DEEPGRAM_STATUS_CODES:
            raise
        logger.info("deepgram_direct_format_rejected", status_code=exc.status_code)

    suffix = Path(original_filename).suffix[:16]
    with TemporaryDirectory(prefix="interview-audio-") as temporary_directory:
        logger.info("recording_normalization_started")
        source_path = Path(temporary_directory) / f"source{suffix}"
        normalized_path = Path(temporary_directory) / "normalized.flac"
        timeout = httpx.Timeout(120, read=600)
        async with (
            httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client,
            client.stream("GET", audio_url) as response,
        ):
            response.raise_for_status()
            with source_path.open("wb") as source_file:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    source_file.write(chunk)

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "flac",
            str(normalized_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace")[-500:]
            raise ValueError(f"Recording format could not be normalized: {detail}")
        logger.info("recording_normalization_succeeded")
        response = await transcriber.transcribe_file(normalized_path)
        logger.info("deepgram_normalized_transcription_succeeded")
        return response


async def claim_recording(settings: Settings, recording_id: UUID) -> RecordingWork | None:
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        async with connection.transaction():
            row = await connection.fetchrow(
                """
                select recordings.id,
                       recordings.storage_provider,
                       recordings.storage_container,
                       recordings.storage_path,
                       recordings.original_filename,
                       recordings.stage,
                       candidates.category,
                       transcripts.text as transcript
                from public.recordings
                join public.candidates on candidates.id = recordings.candidate_id
                left join public.transcripts on transcripts.recording_id = recordings.id
                where recordings.id = $1
                for update of recordings
                """,
                recording_id,
            )
            if row is None or row["stage"] == "completed":
                return None

            transcript = row["transcript"]
            stage = "analyzing" if transcript else "transcribing"
            await connection.execute(
                """
                update public.recordings
                set stage = $2,
                    attempt_count = attempt_count + 1,
                    last_error = null
                where id = $1
                """,
                recording_id,
                stage,
            )
            await connection.execute(
                """
                insert into public.job_events (recording_id, stage, status, detail)
                values ($1, $2, 'started', $3)
                """,
                recording_id,
                stage,
                "Resuming saved transcript" if transcript else "Submitting recording to Deepgram",
            )
            return RecordingWork(
                recording_id=recording_id,
                storage_provider=StorageProvider(row["storage_provider"]),
                storage_container=row["storage_container"],
                storage_path=row["storage_path"],
                original_filename=row["original_filename"] or "recording",
                transcript=transcript,
                category=(
                    CandidateCategory(row["category"])
                    if row["category"] is not None
                    else None
                ),
            )
    finally:
        await connection.close()


async def save_transcript(
    settings: Settings,
    recording_id: UUID,
    transcript: TranscriptPayload,
) -> None:
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        async with connection.transaction():
            await connection.execute(
                """
                insert into public.transcripts (
                  recording_id, text, words, language, provider_meta
                ) values ($1, $2, $3::jsonb, $4, $5::jsonb)
                on conflict (recording_id) do update set
                  text = excluded.text,
                  words = excluded.words,
                  language = excluded.language,
                  provider_meta = excluded.provider_meta
                """,
                recording_id,
                transcript.text,
                json.dumps(transcript.words),
                transcript.language,
                json.dumps(transcript.provider_meta),
            )
            await connection.execute(
                """
                update public.recordings
                set stage = 'transcribed', deepgram_request_id = $2
                where id = $1
                """,
                recording_id,
                transcript.request_id,
            )
            await connection.execute(
                """
                insert into public.job_events (recording_id, stage, status, detail)
                values ($1, 'transcribed', 'succeeded', 'Transcript saved')
                """,
                recording_id,
            )
    finally:
        await connection.close()


async def start_analysis(settings: Settings, recording_id: UUID) -> None:
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        async with connection.transaction():
            await connection.execute(
                "update public.recordings set stage = 'analyzing' where id = $1",
                recording_id,
            )
            await connection.execute(
                """
                insert into public.job_events (recording_id, stage, status, detail)
                values ($1, 'analyzing', 'started', 'Submitting transcript to Claude')
                """,
                recording_id,
            )
    finally:
        await connection.close()


async def save_evaluation(
    settings: Settings,
    recording_id: UUID,
    evaluation: EvaluationResult,
) -> None:
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        async with connection.transaction():
            version = await connection.fetchval(
                """
                select coalesce(max(version), 0) + 1
                from public.evaluations
                where recording_id = $1
                """,
                recording_id,
            )
            await connection.execute(
                "update public.evaluations set is_current = false where recording_id = $1",
                recording_id,
            )
            await connection.execute(
                """
                insert into public.evaluations (
                  recording_id, version, overall_score, scores, summary, strengths,
                  concerns, recommendation, prompt_version, model, token_usage
                ) values (
                  $1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, $11::jsonb
                )
                """,
                recording_id,
                version,
                evaluation.overall_score,
                json.dumps(evaluation.scores.model_dump(mode="json")),
                evaluation.summary,
                evaluation.strengths,
                evaluation.concerns,
                evaluation.recommendation,
                INTERVIEW_PROMPT_VERSION,
                settings.claude_model,
                json.dumps(evaluation.token_usage.model_dump(mode="json")),
            )
            await connection.execute(
                "update public.recordings set stage = 'completed', last_error = null where id = $1",
                recording_id,
            )
            await connection.execute(
                """
                insert into public.job_events (recording_id, stage, status, detail)
                values ($1, 'completed', 'succeeded', 'Evaluation saved')
                """,
                recording_id,
            )
    finally:
        await connection.close()


async def mark_failed(
    settings: Settings,
    recording_id: UUID,
    detail: str,
    will_retry: bool,
) -> None:
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        async with connection.transaction():
            await connection.execute(
                "update public.recordings set stage = 'failed', last_error = $2 where id = $1",
                recording_id,
                detail,
            )
            await connection.execute(
                """
                insert into public.job_events (recording_id, stage, status, detail)
                values ($1, 'failed', $2, $3)
                """,
                recording_id,
                "retry" if will_retry else "failed",
                detail,
            )
    finally:
        await connection.close()


async def process_recording(ctx: dict[str, Any], recording_id: str) -> None:
    settings: Settings = ctx["settings"]
    parsed_recording_id = UUID(recording_id)
    job_try = int(ctx.get("job_try", 1))
    structlog.contextvars.bind_contextvars(recording_id=recording_id, job_try=job_try)
    try:
        work = await claim_recording(settings, parsed_recording_id)
        if work is None:
            logger.info("recording_pipeline_skipped", reason="missing_or_completed")
            return

        transcript_text = work.transcript
        logger.info("recording_pipeline_started", resumed_from_transcript=bool(transcript_text))
        if not transcript_text:
            logger.info("deepgram_transcription_started")
            audio_url = await create_signed_recording_url(ctx["storage"], settings, work)
            response = await transcribe_with_fallback(
                ctx["deepgram"], audio_url, work.original_filename
            )
            transcript = extract_transcript(response)
            await save_transcript(settings, parsed_recording_id, transcript)
            transcript_text = transcript.text
            logger.info(
                "transcript_saved",
                characters=len(transcript.text),
                language=transcript.language,
                deepgram_request_id=transcript.request_id,
            )
            await start_analysis(settings, parsed_recording_id)

        logger.info("claude_analysis_started", model=settings.claude_model)
        evaluation = await ctx["claude"].analyze(transcript_text, work.category)
        await save_evaluation(settings, parsed_recording_id, evaluation)
        logger.info(
            "recording_pipeline_completed",
            model=settings.claude_model,
            overall_score=evaluation.overall_score,
            recommendation=evaluation.recommendation,
            input_tokens=evaluation.token_usage.input_tokens,
            output_tokens=evaluation.token_usage.output_tokens,
            cache_creation_input_tokens=(
                evaluation.token_usage.cache_creation_input_tokens
            ),
            cache_read_input_tokens=evaluation.token_usage.cache_read_input_tokens,
            prompt_cache_hit=evaluation.token_usage.cache_hit,
        )
    except Exception as exc:
        will_retry = job_try <= len(RETRY_DELAYS_SECONDS)
        detail = f"{type(exc).__name__}: {exc}"[:1000]
        await mark_failed(settings, parsed_recording_id, detail, will_retry)
        logger.exception(
            "recording_pipeline_failed",
            recording_id=recording_id,
            job_try=job_try,
            will_retry=will_retry,
        )
        if will_retry:
            raise Retry(defer=RETRY_DELAYS_SECONDS[job_try - 1]) from exc
        raise
    finally:
        structlog.contextvars.clear_contextvars()
