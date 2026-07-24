from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from arq import Retry

from api.app.config import Settings
from api.app.schemas.candidates import CandidateCategory, StorageProvider
from worker.integrations.claude_sdk import EvaluationResult
from worker.pipeline import (
    RecordingWork,
    create_signed_recording_url,
    extract_transcript,
    process_recording,
)

RECORDING_ID = UUID("00000000-0000-0000-0000-000000000005")
DEEPGRAM_RESPONSE = {
    "metadata": {"request_id": "deepgram-request"},
    "results": {
        "channels": [
            {
                "detected_language": "en",
                "alternatives": [
                    {
                        "transcript": "Hello. I would use a transaction.",
                        "words": [{"word": "Hello", "speaker": 0}],
                    }
                ],
            }
        ],
        "utterances": [
            {"speaker": 0, "transcript": "Hello."},
            {"speaker": 1, "transcript": "I would use a transaction."},
        ],
    },
}


def evaluation() -> EvaluationResult:
    return EvaluationResult.model_validate(
        {
            "overall_score": 4,
            "scores": {
                key: {"score": 4, "rationale": "Evidence"}
                for key in [
                    "project_deep_dive",
                    "fundamentals",
                    "live_problem",
                    "learning_ability_and_trends",
                    "candidate_questions",
                ]
            },
            "summary": "Strong interview",
            "strengths": ["Clear reasoning"],
            "concerns": [],
            "recommendation": "selected",
            "token_usage": {
                "input_tokens": 25,
                "output_tokens": 80,
                "cache_creation_input_tokens": 1_500,
                "cache_read_input_tokens": 0,
                "total_input_tokens": 1_525,
                "cache_hit": False,
                "total_cost_usd": 0.01,
            },
        }
    )


def test_extract_transcript_preserves_diarized_utterances() -> None:
    transcript = extract_transcript(DEEPGRAM_RESPONSE)

    assert transcript.text == "Speaker 0: Hello.\nSpeaker 1: I would use a transaction."
    assert transcript.language == "en"
    assert transcript.request_id == "deepgram-request"
    assert transcript.words[0]["speaker"] == 0


@pytest.mark.asyncio
async def test_azure_recording_uses_read_only_sas_url() -> None:
    settings = Settings(
        recording_storage_provider="azure",
        azure_storage_account_name="intervuetest",
    )
    work = RecordingWork(
        RECORDING_ID,
        "panel/job/interview.m4a",
        "interview.m4a",
        None,
        StorageProvider.AZURE,
        "recordings",
    )
    with patch(
        "worker.pipeline.create_azure_read_url",
        new=AsyncMock(return_value="https://azure.example/interview?sas"),
    ) as azure_url_mock:
        url = await create_signed_recording_url(object(), settings, work)

    assert url == "https://azure.example/interview?sas"
    azure_url_mock.assert_awaited_once_with(settings, work.storage_path)


@pytest.mark.asyncio
async def test_process_recording_runs_transcription_then_analysis() -> None:
    settings = Settings(database_url="postgresql://test", claude_model="claude-sonnet-4-6")
    claude = AsyncMock()
    claude.analyze.return_value = evaluation()
    ctx = {
        "settings": settings,
        "storage": object(),
        "deepgram": object(),
        "claude": claude,
        "job_try": 1,
    }
    work = RecordingWork(
        RECORDING_ID,
        "panel/job/interview.m4a",
        "interview.m4a",
        None,
        category=CandidateCategory.AI_ML,
    )

    with patch("worker.pipeline.claim_recording", new=AsyncMock(return_value=work)), patch(
        "worker.pipeline.create_signed_recording_url",
        new=AsyncMock(return_value="https://signed.example/audio"),
    ), patch(
        "worker.pipeline.transcribe_with_fallback",
        new=AsyncMock(return_value=DEEPGRAM_RESPONSE),
    ), patch("worker.pipeline.save_transcript", new=AsyncMock()) as save_transcript_mock, patch(
        "worker.pipeline.start_analysis", new=AsyncMock()
    ) as start_analysis_mock, patch(
        "worker.pipeline.save_evaluation", new=AsyncMock()
    ) as save_evaluation_mock:
        await process_recording(ctx, str(RECORDING_ID))

    save_transcript_mock.assert_awaited_once()
    start_analysis_mock.assert_awaited_once_with(settings, RECORDING_ID)
    claude.analyze.assert_awaited_once_with(
        "Speaker 0: Hello.\nSpeaker 1: I would use a transaction.",
        CandidateCategory.AI_ML,
    )
    save_evaluation_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_recording_marks_retryable_failure() -> None:
    settings = Settings(database_url="postgresql://test")
    ctx = {"settings": settings, "job_try": 1}

    with patch(
        "worker.pipeline.claim_recording", new=AsyncMock(side_effect=OSError("temporary"))
    ), patch(
        "worker.pipeline.mark_failed", new=AsyncMock()
    ) as mark_failed_mock, pytest.raises(Retry):
        await process_recording(ctx, str(RECORDING_ID))

    assert mark_failed_mock.await_args.args[3] is True
