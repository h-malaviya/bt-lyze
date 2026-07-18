import asyncio
import json
from uuid import UUID, uuid4

import asyncpg

from api.app.config import get_settings


async def set_claims(
    connection: asyncpg.Connection,
    role: str,
    panel_id: str | None = None,
) -> None:
    app_metadata = {"role": role}
    if panel_id:
        app_metadata["panel_id"] = panel_id
    claims = {
        "sub": str(uuid4()),
        "role": "authenticated",
        "aud": "authenticated",
        "app_metadata": app_metadata,
    }
    await connection.execute(
        "select set_config('request.jwt.claims', $1, true)",
        json.dumps(claims),
    )
    await connection.execute("set local role authenticated")


async def required_candidate_field_is_enforced(
    connection: asyncpg.Connection,
    panel_id: UUID,
    external_id: str | None,
    category: str | None,
) -> bool:
    savepoint = connection.transaction()
    await savepoint.start()
    try:
        await connection.execute(
            """
            insert into public.candidates (full_name, external_id, category, panel_id)
            values ('Invalid candidate', $1, $2, $3)
            """,
            external_id,
            category,
            panel_id,
        )
        return False
    except asyncpg.IntegrityConstraintViolationError:
        return True
    finally:
        await savepoint.rollback()


async def run() -> int:
    settings = get_settings()
    connection = await asyncpg.connect(settings.database_url, timeout=20)
    transaction = connection.transaction()
    await transaction.start()
    checks: dict[str, bool] = {}
    try:
        existing_candidate_count = await connection.fetchval(
            "select count(*) from public.candidates"
        )
        existing_job_event_count = await connection.fetchval(
            "select count(*) from public.job_events"
        )
        panel_a = await connection.fetchval(
            "insert into public.panels (name) values ('RLS Test A') returning id"
        )
        panel_b = await connection.fetchval(
            "insert into public.panels (name) values ('RLS Test B') returning id"
        )
        candidate_a = await connection.fetchval(
            """
            insert into public.candidates (full_name, external_id, category, panel_id, notes)
            values (
              'Rollback Candidate A', 'ROLL-A', 'ai_ml', $1,
              'distributed systems specialist'
            )
            returning id
            """,
            panel_a,
        )
        await connection.execute(
            """
            insert into public.candidates (full_name, external_id, category, panel_id)
            values ('Rollback Candidate B', 'ROLL-B', 'full_stack_engineer', $1)
            """,
            panel_b,
        )
        recording_id = await connection.fetchval(
            """
            insert into public.recordings (candidate_id, storage_path, stage)
            values ($1, $2, 'completed') returning id
            """,
            candidate_a,
            f"recordings/{panel_a}/{candidate_a}/test.mp3",
        )
        await connection.execute(
            """
            insert into public.transcripts (recording_id, text, language)
            values ($1, 'Candidate explains a reliable queue.', 'en')
            """,
            recording_id,
        )
        await connection.execute(
            """
            insert into public.evaluations (
              recording_id, overall_score, scores, summary, prompt_version, recommendation
            ) values ($1, 8.0, $2::jsonb, 'Strong systems reasoning.', 'rubric_v1', 'selected')
            """,
            recording_id,
            json.dumps(
                {
                    "technical": {"score": 8, "rationale": "Strong"},
                    "communication": {"score": 8, "rationale": "Clear"},
                    "problem_solving": {"score": 8, "rationale": "Methodical"},
                    "culture": {"score": 8, "rationale": "Collaborative"},
                }
            ),
        )
        await connection.execute(
            """
            insert into public.job_events (recording_id, stage, status)
            values ($1, 'completed', 'succeeded')
            """,
            recording_id,
        )

        checks["relationships"] = bool(recording_id)
        checks["default_verdict_selected"] = (
            await connection.fetchval(
                "select verdict::text from public.candidates where id = $1",
                candidate_a,
            )
            == "selected"
        )
        checks["candidate_id_required"] = await required_candidate_field_is_enforced(
            connection,
            panel_a,
            None,
            "ai_ml",
        )
        checks["candidate_category_required"] = await required_candidate_field_is_enforced(
            connection,
            panel_a,
            "ROLL-MISSING-CATEGORY",
            None,
        )
        checks["full_text_search"] = bool(
            await connection.fetchval(
                """
                select exists(
                  select 1 from public.candidates
                  where search_tsv @@ websearch_to_tsquery('english', 'distributed systems')
                )
                """
            )
        )
        before_update = await connection.fetchval(
            "select updated_at from public.candidates where id = $1", candidate_a
        )
        await connection.execute(
            "update public.candidates set notes = notes || ' updated' where id = $1", candidate_a
        )
        after_update = await connection.fetchval(
            "select updated_at from public.candidates where id = $1", candidate_a
        )
        checks["updated_at_trigger"] = after_update >= before_update

        await set_claims(connection, "panel", str(panel_a))
        checks["panel_candidate_isolation"] = (
            await connection.fetchval("select count(*) from public.candidates") == 1
        )
        checks["panel_related_data"] = all(
            [
                await connection.fetchval("select count(*) from public.recordings") == 1,
                await connection.fetchval("select count(*) from public.transcripts") == 1,
                await connection.fetchval("select count(*) from public.evaluations") == 1,
            ]
        )
        checks["panel_job_events_hidden"] = (
            await connection.fetchval("select count(*) from public.job_events") == 0
        )
        checks["panel_cannot_update_other"] = (
            await connection.execute(
                "update public.candidates set notes = 'forbidden' where panel_id = $1", panel_b
            )
            == "UPDATE 0"
        )

        await connection.execute("reset role")
        await set_claims(connection, "admin")
        checks["admin_sees_all_candidates"] = (
            await connection.fetchval("select count(*) from public.candidates")
            == existing_candidate_count + 2
        )
        checks["admin_sees_job_events"] = (
            await connection.fetchval("select count(*) from public.job_events")
            == existing_job_event_count + 1
        )

        output = {"ok": all(checks.values()), "checks": checks, "rolled_back": True}
        print(json.dumps(output, indent=2))
        return 0 if output["ok"] else 1
    finally:
        await transaction.rollback()
        await connection.close()


def main() -> None:
    try:
        raise SystemExit(asyncio.run(run()))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
