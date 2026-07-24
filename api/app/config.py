from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Interview Evaluation API"
    environment: str = "development"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    vite_supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    database_url: str = ""
    recordings_bucket: str = "recordings"
    transcripts_bucket: str = "transcripts"
    recording_storage_provider: Literal["supabase", "azure"] = "supabase"
    azure_storage_account_name: str = ""
    azure_storage_container: str = "recordings"
    azure_storage_connection_string: str = ""
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_upload_sas_ttl_seconds: int = 15 * 60
    azure_read_sas_ttl_seconds: int = 2 * 60 * 60
    redis_url: str = "redis://redis:6379/0"
    deepgram_callback_secret: str = ""
    deepgram_api_key: str = ""
    claude_code_oauth_token: str = ""
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    max_recording_size_bytes: int = 500 * 1024 * 1024
    recording_signed_url_ttl_seconds: int = 2 * 60 * 60
    log_level: str = "INFO"
    log_file: str = ""
    log_max_bytes: int = 25 * 1024 * 1024
    log_backup_count: int = 5
    public_base_url: str = ""
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173","https://exonerate-tucking-sprinkled.ngrok-free.dev"])

    @property
    def browser_publishable_key(self) -> str:
        return self.vite_supabase_anon_key or self.supabase_anon_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
