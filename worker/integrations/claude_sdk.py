import asyncio
import json
from typing import Literal

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from api.app.schemas.candidates import CandidateCategory
from worker.integrations.interview_flow_prompt import (
    INTERVIEW_FLOW_RUBRIC,
    INTERVIEW_PROMPT_VERSION,
)

EvaluationScore = Literal[1, 2, 4, 5]


class CategoryScore(BaseModel):
    score: EvaluationScore
    rationale: str = Field(min_length=1)


class EvaluationScores(BaseModel):
    project_deep_dive: CategoryScore
    fundamentals: CategoryScore
    live_problem: CategoryScore
    learning_ability_and_trends: CategoryScore
    candidate_questions: CategoryScore


class EvaluationContent(BaseModel):
    overall_score: EvaluationScore
    scores: EvaluationScores
    summary: str = Field(min_length=1)
    strengths: list[str]
    concerns: list[str]
    recommendation: Literal["selected", "not_selected", "borderline"]


class TokenUsage(BaseModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_creation_input_tokens: int = Field(default=0, ge=0)
    cache_read_input_tokens: int = Field(default=0, ge=0)
    total_input_tokens: int = Field(default=0, ge=0)
    cache_hit: bool = False
    total_cost_usd: float | None = Field(default=None, ge=0)


class EvaluationResult(EvaluationContent):
    token_usage: TokenUsage = Field(default_factory=TokenUsage)


_EVALUATION_SCHEMA = json.dumps(
    EvaluationContent.model_json_schema(),
    separators=(",", ":"),
    sort_keys=True,
)
_EVALUATION_SYSTEM_PROMPT = (
    f"Prompt version: {INTERVIEW_PROMPT_VERSION}\n"
    "You are an interview evaluation engine. Follow this fixed rubric exactly.\n\n"
    f"{INTERVIEW_FLOW_RUBRIC}\n\n"
    "The JSON must conform exactly to this schema:\n"
    f"{_EVALUATION_SCHEMA}"
)


def parse_evaluation_result(raw_result: str) -> EvaluationResult:
    """Validate the first JSON object and disregard CLI wrapper text."""
    object_start = raw_result.find("{")
    if object_start < 0:
        raise ValueError("Claude analysis returned no JSON object")
    value, _ = json.JSONDecoder().raw_decode(raw_result[object_start:])
    return EvaluationResult.model_validate(value)


def extract_token_usage(result_message: ResultMessage) -> TokenUsage:
    usage = result_message.usage or {}

    def token_count(name: str) -> int:
        value = usage.get(name, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return 0
        return max(0, int(value))

    input_tokens = token_count("input_tokens")
    cache_creation_tokens = token_count("cache_creation_input_tokens")
    cache_read_tokens = token_count("cache_read_input_tokens")
    total_input_tokens = input_tokens + cache_creation_tokens + cache_read_tokens
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=token_count("output_tokens"),
        cache_creation_input_tokens=cache_creation_tokens,
        cache_read_input_tokens=cache_read_tokens,
        total_input_tokens=total_input_tokens,
        cache_hit=cache_read_tokens > 0,
        total_cost_usd=result_message.total_cost_usd,
    )


class ClaudeAnalyzer:
    def __init__(self, oauth_token: str, model: str = "sonnet") -> None:
        if not oauth_token:
            raise ValueError("Claude Code OAuth token is required")
        self._oauth_token = oauth_token
        self._model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=20),
        retry=retry_if_exception_type((OSError, TimeoutError)),
        reraise=True,
    )
    async def analyze(
        self,
        transcript: str,
        category: CandidateCategory | None = None,
    ) -> EvaluationResult:
        if not transcript.strip():
            raise ValueError("Transcript cannot be empty")

        options = ClaudeAgentOptions(
            model=self._model,
            max_turns=1,
            tools=[],
            allowed_tools=[],
            setting_sources=[],
            system_prompt=_EVALUATION_SYSTEM_PROMPT,
            env={"CLAUDE_CODE_OAUTH_TOKEN": self._oauth_token},
        )

        category_label = {
            CandidateCategory.AI_ML: "AI/ML",
            CandidateCategory.FULL_STACK_ENGINEER: "Full Stack Engineer",
        }.get(category, "Unspecified role")
        prompt = (
            f"Evaluate this diarized interview for the {category_label} category. "
            "Apply domain expectations appropriate to that category.\n\n"
            f"TRANSCRIPT:\n{transcript}"
        )
        result_message: ResultMessage | None = None
        async with asyncio.timeout(180):
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    result_message = message

        if result_message is None or result_message.is_error:
            raise RuntimeError("Claude analysis did not complete successfully")
        if not result_message.result:
            raise RuntimeError("Claude analysis returned no result")
        evaluation = parse_evaluation_result(result_message.result)
        return evaluation.model_copy(
            update={"token_usage": extract_token_usage(result_message)}
        )
