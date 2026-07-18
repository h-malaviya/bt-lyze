from collections.abc import Sequence

import asyncpg
import structlog
from arq.connections import ArqRedis

from api.app.config import Settings

logger = structlog.get_logger()


async def pending_outbox_ids(settings: Settings, limit: int = 50) -> Sequence[int]:
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        rows = await connection.fetch(
            """
            select id
            from public.job_outbox
            where status = 'pending' and available_at <= now()
            order by id
            limit $1
            """,
            limit,
        )
        return [row["id"] for row in rows]
    finally:
        await connection.close()


async def dispatch_outbox_job(
    settings: Settings,
    redis: ArqRedis,
    outbox_id: int,
) -> bool:
    connection = await asyncpg.connect(settings.database_url, timeout=15)
    try:
        row = await connection.fetchrow(
            """
            select recording_id, job_name
            from public.job_outbox
            where id = $1 and status = 'pending' and available_at <= now()
            """,
            outbox_id,
        )
        if row is None:
            return False

        recording_id = str(row["recording_id"])
        job = await redis.enqueue_job(
            row["job_name"],
            recording_id,
            _job_id=f"process_recording:{recording_id}",
        )
        await connection.execute(
            """
            update public.job_outbox
            set status = 'dispatched',
                dispatched_at = now(),
                attempt_count = attempt_count + 1,
                last_error = null
            where id = $1
            """,
            outbox_id,
        )
        logger.info(
            "outbox_job_dispatched",
            outbox_id=outbox_id,
            recording_id=recording_id,
            redis_job_created=job is not None,
        )
        return True
    except Exception as exc:
        await connection.execute(
            """
            update public.job_outbox
            set attempt_count = attempt_count + 1,
                last_error = $2,
                available_at = now() + interval '15 seconds'
            where id = $1 and status = 'pending'
            """,
            outbox_id,
            f"{type(exc).__name__}: {exc}"[:1000],
        )
        raise
    finally:
        await connection.close()
