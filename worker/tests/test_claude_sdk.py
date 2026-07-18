from unittest.mock import patch

import pytest
from claude_agent_sdk import ResultMessage
from pydantic import ValidationError

from api.app.schemas.candidates import CandidateCategory
from worker.integrations.claude_sdk import (
    _EVALUATION_SYSTEM_PROMPT,
    ClaudeAnalyzer,
    EvaluationResult,
    extract_token_usage,
    parse_evaluation_result,
)

EVALUATION_JSON = """{"overall_score":4,"scores":{"project_deep_dive":{"score":4,
"rationale":"A"},"fundamentals":{"score":4,"rationale":"B"},"live_problem":{"score":4,
"rationale":"C"},"learning_ability_and_trends":{"score":4,"rationale":"D"},
"candidate_questions":{"score":4,"rationale":"E"}},"summary":"Good",
"strengths":[],"concerns":[],"recommendation":"selected"}"""

EVALUATION_CATEGORIES = [
    "project_deep_dive",
    "fundamentals",
    "live_problem",
    "learning_ability_and_trends",
    "candidate_questions",
]


def result_message(**overrides: object) -> ResultMessage:
    values = {
        "subtype": "success",
        "duration_ms": 10,
        "duration_api_ms": 8,
        "is_error": False,
        "num_turns": 1,
        "session_id": "session",
        "result": EVALUATION_JSON,
    }
    values.update(overrides)
    return ResultMessage(**values)


def test_evaluation_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(
            {
                "overall_score": 6,
                "scores": {
                    key: {"score": 4, "rationale": "Evidence"}
                    for key in EVALUATION_CATEGORIES
                },
                "summary": "Summary",
                "strengths": [],
                "concerns": [],
                "recommendation": "selected",
            }
        )


def test_evaluation_rejects_decimal_score() -> None:
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(
            {
                "overall_score": 4,
                "scores": {
                    key: {
                        "score": 4.5 if key == "fundamentals" else 4,
                        "rationale": "Evidence",
                    }
                    for key in EVALUATION_CATEGORIES
                },
                "summary": "Summary",
                "strengths": [],
                "concerns": [],
                "recommendation": "selected",
            }
        )


@pytest.mark.asyncio
async def test_analyzer_rejects_empty_transcript_before_sdk_call() -> None:
    analyzer = ClaudeAnalyzer("test-token")

    with pytest.raises(ValueError, match="Transcript cannot be empty"):
        await analyzer.analyze("  ")


def test_result_parser_ignores_cli_trailing_output() -> None:
    result = parse_evaluation_result(f"```json\n{EVALUATION_JSON}\n``` trailing")

    assert result.overall_score == 4


def test_system_prompt_uses_junior_calibration_and_bullet_summary() -> None:
    normalized_prompt = " ".join(_EVALUATION_SYSTEM_PROMPT.split())

    assert _EVALUATION_SYSTEM_PROMPT.startswith("Prompt version: interview-v8\n")
    assert (
        "Calibrate every score for an intern or junior-level hiring decision"
        in normalized_prompt
    )
    assert "complete pattern of relevant observations" in normalized_prompt
    assert "between two and four concise Markdown bullet points" in normalized_prompt
    assert "no more than 18 words" in normalized_prompt
    assert "no more than 70 words" in normalized_prompt
    assert "limit each bullet to one sentence and 20 words" in normalized_prompt
    assert "no more than four strengths and four concerns" in normalized_prompt
    assert "discrete scale from 1 through 5" in normalized_prompt
    assert "Use 3 only when the evidence is genuinely mixed" in normalized_prompt


def test_extract_token_usage_includes_prompt_cache_counters() -> None:
    usage = extract_token_usage(
        result_message(
            usage={
                "input_tokens": 25,
                "output_tokens": 80,
                "cache_creation_input_tokens": 1_500,
                "cache_read_input_tokens": 2_000,
            },
            total_cost_usd=0.0123,
        )
    )

    assert usage.input_tokens == 25
    assert usage.output_tokens == 80
    assert usage.total_input_tokens == 3_525
    assert usage.cache_hit is True
    assert usage.total_cost_usd == 0.0123


@pytest.mark.asyncio
async def test_analyzer_reuses_static_prompt_and_attaches_usage() -> None:
    calls: list[tuple[str, object]] = []

    async def fake_query(*, prompt: str, options: object):
        calls.append((prompt, options))
        yield result_message(
            usage={
                "input_tokens": 10,
                "output_tokens": 20,
                "cache_read_input_tokens": 500,
            }
        )

    analyzer = ClaudeAnalyzer("test-token", "claude-sonnet-4-6")
    with patch("worker.integrations.claude_sdk.query", new=fake_query):
        first = await analyzer.analyze("Candidate: First answer", CandidateCategory.AI_ML)
        await analyzer.analyze(
            "Candidate: Second answer",
            CandidateCategory.FULL_STACK_ENGINEER,
        )

    assert calls[0][1].system_prompt == calls[1][1].system_prompt
    assert "First answer" not in calls[0][1].system_prompt
    assert calls[0][0] != calls[1][0]
    assert "AI/ML category" in calls[0][0]
    assert "Full Stack Engineer category" in calls[1][0]
    assert first.token_usage.output_tokens == 20
    assert first.token_usage.cache_hit is True
