from typing import Any, ClassVar

import asyncpg
import structlog
from arq import cron
from arq.connections import RedisSettings
from redis.exceptions import RedisError
from supabase import create_client

from api.app.config import get_settings
from api.app.logging import configure_logging
from api.app.services.job_queue import dispatch_outbox_job, pending_outbox_ids
from worker.integrations.claude_sdk import ClaudeAnalyzer
from worker.integrations.deepgram import DeepgramTranscriber
from worker.pipeline import process_recording

settings = get_settings()
configure_logging(settings, "worker")
logger = structlog.get_logger()
ARQ_LOG_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        "arq": {
            "handlers": [],
            "level": settings.log_level.upper(),
            "propagate": True,
        }
    },
}


async def startup(ctx: dict[str, Any]) -> None:
    ctx["settings"] = settings
    ctx["deepgram"] = DeepgramTranscriber(settings.deepgram_api_key)
    ctx["claude"] = ClaudeAnalyzer(
        oauth_token=settings.claude_code_oauth_token,
        model=settings.claude_model,
    )
    ctx["storage"] = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    logger.info("worker_started", concurrency=1, claude_model=settings.claude_model)


async def shutdown(_: dict[str, object]) -> None:
    logger.info("worker_stopped")


async def dispatch_pending_jobs(ctx: dict[str, Any]) -> None:
    settings = ctx["settings"]
    for outbox_id in await pending_outbox_ids(settings):
        try:
            await dispatch_outbox_job(settings, ctx["redis"], outbox_id)
        except (asyncpg.PostgresError, RedisError, OSError, TimeoutError):
            logger.exception("outbox_dispatch_failed", outbox_id=outbox_id)


class WorkerSettings:
    functions: ClassVar = [process_recording]
    cron_jobs: ClassVar = [
        cron(
            dispatch_pending_jobs,
            second={0, 10, 20, 30, 40, 50},
            run_at_startup=True,
        )
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 1
    max_tries = 3
    job_timeout = 2 * 60 * 60
    keep_result = 0
