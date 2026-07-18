from __future__ import annotations

import argparse
import asyncio
import json
from uuid import UUID

import asyncpg
from supabase import create_client

from api.app.config import get_settings


async def run(user_id: UUID, panel_name: str) -> int:
    settings = get_settings()
    if not settings.database_url or not settings.supabase_service_role_key:
        raise RuntimeError("Database and Supabase service credentials are required")

    connection = await asyncpg.connect(settings.database_url, timeout=20)
    try:
        async with connection.transaction():
            panel_id = await connection.fetchval(
                "select id from public.panels where auth_user_id = $1",
                user_id,
            )
            if panel_id is None:
                panel_id = await connection.fetchval(
                    """
                    insert into public.panels (name, auth_user_id)
                    values ($1, $2)
                    returning id
                    """,
                    panel_name,
                    user_id,
                )
    finally:
        await connection.close()

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    user_response = await asyncio.to_thread(supabase.auth.admin.get_user_by_id, str(user_id))
    app_metadata = dict(user_response.user.app_metadata or {})
    app_metadata.update({"role": "panel", "panel_id": str(panel_id)})
    await asyncio.to_thread(
        supabase.auth.admin.update_user_by_id,
        str(user_id),
        {"app_metadata": app_metadata},
    )

    connection = await asyncpg.connect(settings.database_url, timeout=20)
    try:
        profile_panel_id = await connection.fetchval(
            "select panel_id from public.profiles where id = $1",
            user_id,
        )
    finally:
        await connection.close()

    checks = {
        "panel_created": panel_id is not None,
        "auth_metadata_assigned": profile_panel_id == panel_id,
        "panel_id": str(panel_id),
    }
    ok = all(checks[name] for name in ("panel_created", "auth_metadata_assigned"))
    print(json.dumps({"ok": ok, "checks": checks}, indent=2))
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--name", default="panel1")
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(run(args.user_id, args.name)))
    except Exception as exc:
        settings = get_settings()
        detail = str(exc)
        for secret in (settings.database_url, settings.supabase_service_role_key):
            if secret:
                detail = detail.replace(secret, "<redacted>")
        print(json.dumps({"ok": False, "error": type(exc).__name__, "detail": detail}))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
