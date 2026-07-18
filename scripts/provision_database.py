from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import asyncpg

from api.app.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "panels",
    "profiles",
    "candidates",
    "recordings",
    "transcripts",
    "evaluations",
    "job_events",
    "job_outbox",
}


async def verify(connection: asyncpg.Connection[asyncpg.Record]) -> dict[str, object]:
    tables = {
        row["tablename"]
        for row in await connection.fetch(
            "select tablename from pg_tables where schemaname = 'public'"
        )
    }
    rls_tables = {
        row["relname"]
        for row in await connection.fetch(
            """
            select relname
            from pg_class
            join pg_namespace on pg_namespace.oid = pg_class.relnamespace
            where pg_namespace.nspname = 'public' and pg_class.relrowsecurity
            """
        )
    }
    policy_count = await connection.fetchval(
        """
        select count(*) from pg_policies
        where (schemaname = 'public' and tablename = any($1::text[]))
           or (schemaname = 'storage' and tablename = 'objects')
        """,
        list(EXPECTED_TABLES),
    )
    buckets = await connection.fetch(
        "select id, public from storage.buckets where id = any($1::text[])",
        ["recordings", "transcripts"],
    )
    current_indexes = await connection.fetchval(
        """
        select count(*) from pg_indexes
        where schemaname = 'public'
          and indexname = any($1::text[])
        """,
        [
            "candidates_panel_id_idx",
            "candidates_verdict_idx",
            "candidates_created_at_idx",
            "candidates_search_idx",
            "recordings_candidate_id_idx",
            "recordings_stage_idx",
            "recordings_storage_object_idx",
            "evaluations_recording_id_idx",
            "evaluations_one_current_idx",
            "evaluations_overall_score_idx",
            "job_events_recording_created_idx",
            "job_outbox_pending_idx",
        ],
    )
    transport = getattr(connection, "_transport", None)
    using_ssl = bool(transport and transport.get_extra_info("ssl_object"))
    trigger_exists = await connection.fetchval(
        """
        select exists(
          select 1 from pg_trigger
          where tgname = 'auth_user_created' and not tgisinternal
        )
        """
    )

    checks = {
        "tables": tables >= EXPECTED_TABLES,
        "rls": rls_tables >= EXPECTED_TABLES,
        "policies": policy_count == 16,
        "indexes": current_indexes == 12,
        "private_buckets": len(buckets) == 2 and all(not row["public"] for row in buckets),
        "profile_trigger": trigger_exists,
        "ssl": bool(using_ssl),
    }
    return {"ok": all(checks.values()), "checks": checks}


async def run(apply: bool) -> int:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    connection = await asyncpg.connect(settings.database_url, timeout=20)
    try:
        if apply:
            await connection.execute("select pg_advisory_lock(73198421)")
            try:
                async with connection.transaction():
                    await connection.execute((ROOT / "db" / "schema.sql").read_text("utf-8"))
                    await connection.execute((ROOT / "db" / "policies.sql").read_text("utf-8"))
            finally:
                await connection.execute("select pg_advisory_unlock(73198421)")

        result = await verify(connection)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(run(args.apply)))
    except Exception as exc:
        detail = str(exc)
        settings = get_settings()
        if settings.database_url:
            detail = detail.replace(settings.database_url, "<redacted>")
        print(json.dumps({"ok": False, "error": type(exc).__name__, "detail": detail}))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
