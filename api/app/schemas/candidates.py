from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class Verdict(StrEnum):
    SELECTED = "selected"
    NOT_DECIDED = "not_decided"
    NOT_SELECTED = "not_selected"


class CandidateCategory(StrEnum):
    AI_ML = "ai_ml"
    FULL_STACK_ENGINEER = "full_stack_engineer"


class JobStage(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class StorageProvider(StrEnum):
    SUPABASE = "supabase"
    AZURE = "azure"


class RecordingCreate(BaseModel):
    storage_provider: StorageProvider = StorageProvider.SUPABASE
    storage_container: str | None = Field(default=None, min_length=1, max_length=255)
    storage_path: str = Field(min_length=1, max_length=1024)
    original_filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    mime_type: str | None = Field(default=None, max_length=255)

    @field_validator("storage_container", "storage_path", "original_filename")
    @classmethod
    def normalize_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Recording value is required")
        return normalized


class CandidateCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    external_id: str = Field(min_length=1, max_length=100)
    category: CandidateCategory
    verdict: Verdict = Verdict.SELECTED
    notes: str | None = Field(default=None, max_length=5000)
    recording: RecordingCreate

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Candidate name is required")
        return normalized

    @field_validator("external_id")
    @classmethod
    def normalize_candidate_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Candidate ID is required")
        return normalized

    @field_validator("notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CandidateResponse(BaseModel):
    id: UUID
    external_id: str | None
    full_name: str
    category: CandidateCategory | None
    panel_id: UUID
    panel_name: str
    verdict: Verdict | None
    notes: str | None
    recording_id: UUID | None
    stage: JobStage | None
    overall_score: float | None
    created_at: datetime
    updated_at: datetime


class CandidateListResponse(BaseModel):
    items: list[CandidateResponse]
    total: int
