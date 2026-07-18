from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from api.app.schemas.candidates import StorageProvider


class RecordingUploadRequest(BaseModel):
    candidate_name: str = Field(min_length=1, max_length=200)
    original_filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    mime_type: str | None = Field(default=None, max_length=255)

    @field_validator("candidate_name")
    @classmethod
    def normalize_candidate_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Candidate name is required")
        return normalized

    @field_validator("original_filename")
    @classmethod
    def normalize_filename(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Recording filename is required")
        return normalized


class RecordingUploadGrant(BaseModel):
    storage_provider: StorageProvider
    storage_container: str
    storage_path: str
    upload_url: str | None = None
    upload_headers: dict[str, str] = Field(default_factory=dict)
    expires_at: datetime | None = None


class RecordingUploadCleanupRequest(BaseModel):
    storage_provider: StorageProvider
    storage_container: str = Field(min_length=1, max_length=255)
    storage_path: str = Field(min_length=1, max_length=1024)
