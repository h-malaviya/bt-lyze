from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any
from uuid import UUID

import asyncpg

from api.app.config import get_settings
from worker.integrations.claude_sdk import ClaudeAnalyzer
from worker.pipeline import process_recording

ACTIVE_STAGES = {"queued", "transcribing", "analyzing"}


def _candidate_query(lock_recording: bool) -> str:
    lock_clause = "for update of candidates, latest_recording" if lock_recording else ""
    return f"""
        select candidates.id as candidate_id,
               candidates.full_name,
               latest_recording.id as recording_id,
               latest_recording.stage,
               latest_recording.original_filename,
               transcripts.text as transcript,
               current_evaluation.version as evaluation_version,
               current_evaluation.prompt_version
        from public.candidates
        join public.recordings as latest_recording
          on latest_recording.id = (
            select recordings.id
            from public.recordings
            where recordings.candidate_id = candidates.id
            order by recordings.created_at desc
            limit 1
          )
        left join public.transcripts
          on transcripts.recording_id = latest_recording.id
        left join public.evaluations as current_evaluation
          on current_evaluation.recording_id = latest_recording.id
         and current_evaluation.is_current
        where candidates.id = $1
        {lock_clause}
    """


def _validate_candidate(row: asyncpg.Record | None, expected_name: str) -> asyncpg.Record:
    if row is None:
        raise ValueError("Candidate or recording was not found")
    if row["full_name"].strip().casefold() != expected_name.strip().casefold():
        raise ValueError(
            f"Candidate name mismatch: database contains {row['full_name']!r}"
        )
    if not str(row["transcript"] or "").strip():
        raise ValueError("The latest recording has no saved transcript to reuse")
    if row["stage"] in ACTIVE_STAGES:
        raise ValueError(f"Recording is already active in stage {row['stage']!r}")
    return row


def _result_payload(row: asyncpg.Record, applied: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "applied": applied,
        "candidate_id": str(row["candidate_id"]),
        "candidate_name": row["full_name"],
        "recording_id": str(row["recording_id"]),
        "recording_filename": row["original_filename"],
        "recording_stage": row["stage"],
        "current_evaluation_version": row["evaluation_version"],
        "current_prompt_version": row["prompt_version"],
        "reused_transcript": True,
    }


async def _prepare_rerun(candidate_id: UUID, expected_name: str) -> asyncpg.Record:
    settings = get_settings()
    connection = await asyncpg.connect(settings.database_url, timeout=20)
    try:
        async with connection.transaction():
            row = _validate_candidate(
                await connection.fetchrow(_candidate_query(True), candidate_id),
                expected_name,
            )
            await connection.execute(
                """
                update public.recordings
                set stage = 'queued', last_error = null
                where id = $1
                """,
                row["recording_id"],
            )
            await connection.execute(
                """
                insert into public.job_events (recording_id, stage, status, detail)
                values ($1, 'queued', 'succeeded', 'Manual evaluation rerun requested')
                """,
                row["recording_id"],
            )
            return row
    finally:
        await connection.close()


async def _load_candidate(candidate_id: UUID, expected_name: str) -> asyncpg.Record:
    settings = get_settings()
    connection = await asyncpg.connect(settings.database_url, timeout=20)
    try:
        return _validate_candidate(
            await connection.fetchrow(_candidate_query(False), candidate_id),
            expected_name,
        )
    finally:
        await connection.close()


async def _load_result(candidate_id: UUID) -> dict[str, Any]:
    settings = get_settings()
    connection = await asyncpg.connect(settings.database_url, timeout=20)
    try:
        row = await connection.fetchrow(
            """
            select candidates.id as candidate_id,
                   candidates.full_name as candidate_name,
                   recordings.id as recording_id,
                   recordings.stage,
                   evaluations.version as evaluation_version,
                   evaluations.overall_score,
                   evaluations.recommendation,
                   evaluations.prompt_version
            from public.candidates
            join lateral (
              select recordings.*
              from public.recordings
              where recordings.candidate_id = candidates.id
              order by recordings.created_at desc
              limit 1
            ) as recordings on true
            join public.evaluations
              on evaluations.recording_id = recordings.id
             and evaluations.is_current
            where candidates.id = $1
            """,
            candidate_id,
        )
        if row is None:
            raise RuntimeError("Rerun completed without a current evaluation")
        return {
            "ok": True,
            "applied": True,
            "candidate_id": str(row["candidate_id"]),
            "candidate_name": row["candidate_name"],
            "recording_id": str(row["recording_id"]),
            "recording_stage": row["stage"],
            "evaluation_version": row["evaluation_version"],
            "overall_score": int(row["overall_score"]),
            "recommendation": row["recommendation"],
            "prompt_version": row["prompt_version"],
            "created_candidate": False,
            "created_recording": False,
        }
    finally:
        await connection.close()


async def run(candidate_id: UUID, expected_name: str, apply: bool) -> int:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    if apply and not settings.claude_code_oauth_token:
        raise RuntimeError("CLAUDE_CODE_OAUTH_TOKEN is not configured")

    if not apply:
        row = await _load_candidate(candidate_id, expected_name)
        print(json.dumps(_result_payload(row, False), indent=2, default=str))
        return 0

    row = await _prepare_rerun(candidate_id, expected_name)
    analyzer = ClaudeAnalyzer(
        oauth_token=settings.claude_code_oauth_token,
        model=settings.claude_model,
    )
    await process_recording(
        {"settings": settings, "claude": analyzer, "job_try": 3},
        str(row["recording_id"]),
    )
    print(json.dumps(await _load_result(candidate_id), indent=2, default=str))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rerun evaluation for a candidate's latest recording and saved transcript."
    )
    parser.add_argument("--candidate-id", required=True, type=UUID)
    parser.add_argument("--expected-name", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(run_async(args.candidate_id, args.expected_name, args.apply))
    except Exception as exc:
        settings = get_settings()
        detail = str(exc)
        if settings.database_url:
            detail = detail.replace(settings.database_url, "<redacted>")
        print(
            json.dumps(
                {"ok": False, "error": type(exc).__name__, "detail": detail},
                indent=2,
            )
        )
        raise SystemExit(1) from exc


def run_async(candidate_id: UUID, expected_name: str, apply: bool) -> int:
    return asyncio.run(run(candidate_id, expected_name, apply))


if __name__ == "__main__":
    main()
