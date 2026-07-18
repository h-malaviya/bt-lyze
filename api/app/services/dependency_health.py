import asyncio
from dataclasses import asdict, dataclass
from time import perf_counter

import asyncpg
import httpx

from api.app.config import Settings
from api.app.services.recording_storage import (
    AzureStorageConfigurationError,
    AzureStorageOperationError,
    verify_azure_container,
)


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    ok: bool
    latency_ms: int
    detail: str


async def check_database(settings: Settings) -> DependencyStatus:
    started = perf_counter()
    if not settings.database_url:
        return DependencyStatus("database", False, 0, "not configured")

    try:
        connection = await asyncpg.connect(settings.database_url, timeout=10)
        try:
            table_count = await connection.fetchval(
                """
                select count(*)
                from information_schema.tables
                where table_schema = 'public'
                  and table_name = any($1::text[])
                """,
                [
                    "panels",
                    "profiles",
                    "candidates",
                    "recordings",
                    "transcripts",
                    "evaluations",
                    "job_events",
                    "job_outbox",
                ],
            )
        finally:
            await connection.close()
        return DependencyStatus(
            "database",
            table_count == 8,
            round((perf_counter() - started) * 1000),
            f"{table_count}/8 application tables available",
        )
    except (OSError, asyncpg.PostgresError, TimeoutError):
        return DependencyStatus(
            "database",
            False,
            round((perf_counter() - started) * 1000),
            "connection failed",
        )


async def check_deepgram(settings: Settings) -> DependencyStatus:
    started = perf_counter()
    if not settings.deepgram_api_key:
        return DependencyStatus("deepgram", False, 0, "not configured")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.deepgram.com/v1/projects",
                headers={"Authorization": f"Token {settings.deepgram_api_key}"},
            )
        return DependencyStatus(
            "deepgram",
            response.status_code == 200,
            round((perf_counter() - started) * 1000),
            "authenticated" if response.status_code == 200 else "authentication failed",
        )
    except (httpx.HTTPError, TimeoutError):
        return DependencyStatus(
            "deepgram",
            False,
            round((perf_counter() - started) * 1000),
            "connection failed",
        )


async def check_supabase_auth(settings: Settings) -> DependencyStatus:
    started = perf_counter()
    if not settings.supabase_url:
        return DependencyStatus("supabase_auth", False, 0, "not configured")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            )
        body = response.json() if response.status_code == 200 else {}
        ok = bool(body.get("keys"))
        return DependencyStatus(
            "supabase_auth",
            ok,
            round((perf_counter() - started) * 1000),
            "signing keys available" if ok else "signing keys unavailable",
        )
    except (httpx.HTTPError, ValueError, TimeoutError):
        return DependencyStatus(
            "supabase_auth",
            False,
            round((perf_counter() - started) * 1000),
            "connection failed",
        )


async def check_recording_storage(settings: Settings) -> DependencyStatus:
    started = perf_counter()
    if settings.recording_storage_provider == "supabase":
        return DependencyStatus("recording_storage", True, 0, "Supabase Storage selected")
    try:
        await verify_azure_container(settings)
        return DependencyStatus(
            "recording_storage",
            True,
            round((perf_counter() - started) * 1000),
            (
                "Azure container authenticated with account key"
                if settings.azure_storage_connection_string
                else "Azure container and user delegation authenticated"
            ),
        )
    except (AzureStorageConfigurationError, AzureStorageOperationError):
        return DependencyStatus(
            "recording_storage",
            False,
            round((perf_counter() - started) * 1000),
            "Azure container connection failed",
        )


async def check_runtime_dependencies(settings: Settings) -> list[dict[str, object]]:
    results = await asyncio.gather(
        check_database(settings),
        check_deepgram(settings),
        check_supabase_auth(settings),
        check_recording_storage(settings),
    )
    return [asdict(result) for result in results]
