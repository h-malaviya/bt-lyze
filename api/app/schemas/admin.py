from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from api.app.schemas.candidates import CandidateCategory, JobStage, StorageProvider, Verdict

Recommendation = Literal["selected", "not_selected", "borderline"]
ScoreBand = Literal["4_to_5", "1_to_2", "unscored"]


class AdminMetrics(BaseModel):
    candidates: int
    ready: int
    in_progress: int
    needs_attention: int


class PanelOption(BaseModel):
    id: UUID
    name: str


class AdminCandidateItem(BaseModel):
    id: UUID
    external_id: str | None
    full_name: str
    category: CandidateCategory | None
    panel_id: UUID
    panel_name: str
    verdict: Verdict | None
    recording_id: UUID | None
    stage: JobStage | None
    overall_score: float | None
    recommendation: Recommendation | None
    created_at: datetime
    updated_at: datetime


class AdminCandidateListResponse(BaseModel):
    items: list[AdminCandidateItem]
    total: int
    metrics: AdminMetrics
    panels: list[PanelOption]


class EvaluationCategory(BaseModel):
    score: float
    rationale: str


class AdminTokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    total_input_tokens: int = 0
    cache_hit: bool = False
    total_cost_usd: float | None = None


class AdminEvaluationDetail(BaseModel):
    version: int
    overall_score: float | None
    scores: dict[str, EvaluationCategory]
    summary: str
    strengths: list[str]
    concerns: list[str]
    recommendation: Recommendation | None
    prompt_version: str
    model: str | None
    token_usage: AdminTokenUsage | None
    created_at: datetime


class AdminTranscriptDetail(BaseModel):
    text: str | None
    language: str | None
    created_at: datetime


class AdminRecordingDetail(BaseModel):
    id: UUID
    storage_provider: StorageProvider
    storage_container: str
    original_filename: str | None
    duration_sec: int | None
    size_bytes: int | None
    mime_type: str | None
    stage: JobStage
    attempt_count: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class AdminRecordingPlayback(BaseModel):
    url: str
    expires_at: datetime


class AdminJobEvent(BaseModel):
    id: int
    stage: JobStage | None
    status: Literal["started", "succeeded", "failed", "retry"]
    detail: str | None
    created_at: datetime


class AdminCandidateDetail(BaseModel):
    id: UUID
    external_id: str | None
    full_name: str
    category: CandidateCategory | None
    panel_id: UUID
    panel_name: str
    verdict: Verdict | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    recording: AdminRecordingDetail | None
    transcript: AdminTranscriptDetail | None
    evaluation: AdminEvaluationDetail | None
    events: list[AdminJobEvent]
