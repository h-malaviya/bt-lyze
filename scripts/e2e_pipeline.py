from __future__ import annotations

import asyncio
import json
import secrets
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

import asyncpg
import httpx
import jwt

from api.app.config import Settings, get_settings

SAMPLE_AUDIO_URL = "https://dpgr.am/spacewalk.wav"
LOCAL_APP_URL = "http://localhost:8080"
POLL_INTERVAL_SECONDS = 5
PIPELINE_TIMEOUT_SECONDS = 360


async def _ensure_active_panel(settings: Settings) -> tuple[UUID, bool]:
    connection = await asyncpg.connect(settings.database_url, timeout=20)
    try:
        panel_id = await connection.fetchval(
            "select id from public.panels where is_active order by created_at limit 1"
        )
        if panel_id is not None:
            return panel_id, False
        panel_id = await connection.fetchval(
            "insert into public.panels (name) values ('Pipeline E2E Panel') returning id"
        )
        return panel_id, True
    finally:
        await connection.close()


async def _wait_for_pipeline(settings: Settings, recording_id: UUID) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + PIPELINE_TIMEOUT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        connection = await asyncpg.connect(settings.database_url, timeout=20)
        try:
            row = await connection.fetchrow(
                """
                select recordings.stage,
                       recordings.last_error,
                       recordings.attempt_count,
                       transcripts.text as transcript,
                       evaluations.model,
                       evaluations.overall_score,
                       job_outbox.status as outbox_status
                from public.recordings
                left join public.transcripts on transcripts.recording_id = recordings.id
                left join public.evaluations
                  on evaluations.recording_id = recordings.id and evaluations.is_current
                left join public.job_outbox on job_outbox.recording_id = recordings.id
                where recordings.id = $1
                """,
                recording_id,
            )
        finally:
            await connection.close()

        if row is None:
            raise RuntimeError("End-to-end recording disappeared during processing")
        if row["stage"] == "completed":
            return dict(row)
        if (
            row["stage"] == "failed"
            and row["last_error"]
            and row["attempt_count"] >= 3
        ):
            raise RuntimeError(f"Pipeline failed: {row['last_error']}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError("Pipeline did not complete within six minutes")


async def _delete_candidate(settings: Settings, candidate_id: UUID) -> None:
    connection = await asyncpg.connect(settings.database_url, timeout=20)
    try:
        await connection.execute("delete from public.candidates where id = $1", candidate_id)
    finally:
        await connection.close()


async def _delete_panel(settings: Settings, panel_id: UUID) -> None:
    connection = await asyncpg.connect(settings.database_url, timeout=20)
    try:
        await connection.execute("delete from public.panels where id = $1", panel_id)
    finally:
        await connection.close()


async def run() -> int:
    settings = get_settings()
    required = {
        "SUPABASE_URL": settings.supabase_url,
        "VITE_SUPABASE_ANON_KEY": settings.browser_publishable_key,
        "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
        "DATABASE_URL": settings.database_url,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required settings: {', '.join(missing)}")

    panel_id, created_panel = await _ensure_active_panel(settings)
    test_id = uuid4()
    email = f"codex-e2e-{test_id.hex[:12]}@example.com"
    password = secrets.token_urlsafe(24)
    storage_path = f"{panel_id}/{test_id}/spacewalk.wav"
    storage_provider = "supabase"
    storage_container = settings.recordings_bucket
    user_id: UUID | None = None
    admin_user_id: UUID | None = None
    candidate_id: UUID | None = None
    cleanup_checks: dict[str, bool] = {}
    result: dict[str, Any] = {}

    service_headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        try:
            create_user = await client.post(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users",
                headers=service_headers,
                json={
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "app_metadata": {"role": "panel", "panel_id": str(panel_id)},
                },
            )
            create_user.raise_for_status()
            user_id = UUID(create_user.json()["id"])

            sign_in = await client.post(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
                headers={"apikey": settings.browser_publishable_key},
                json={"email": email, "password": password},
            )
            if sign_in.is_error:
                raise RuntimeError(
                    f"Temporary panel sign-in failed ({sign_in.status_code}): "
                    f"{sign_in.text[:300]}"
                )
            access_token = sign_in.json()["access_token"]

            audio = await client.get(SAMPLE_AUDIO_URL)
            audio.raise_for_status()
            upload_grant = await client.post(
                f"{LOCAL_APP_URL}/api/recordings/upload-url",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "candidate_name": "Pipeline E2E Candidate",
                    "original_filename": "spacewalk.wav",
                    "size_bytes": len(audio.content),
                    "mime_type": "audio/wav",
                },
            )
            upload_grant.raise_for_status()
            grant = upload_grant.json()
            storage_provider = grant["storage_provider"]
            storage_container = grant["storage_container"]
            storage_path = grant["storage_path"]
            if storage_provider == "azure":
                upload_headers = {
                    **grant["upload_headers"],
                    "Content-Type": "audio/wav",
                }
                upload = await client.put(
                    grant["upload_url"],
                    headers=upload_headers,
                    content=audio.content,
                )
            else:
                upload = await client.post(
                    f"{settings.supabase_url.rstrip('/')}/storage/v1/object/"
                    f"{storage_container}/{quote(storage_path, safe='/')}",
                    headers={
                        "apikey": settings.browser_publishable_key,
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "audio/wav",
                        "x-upsert": "false",
                    },
                    content=audio.content,
                )
            upload.raise_for_status()

            create_candidate = await client.post(
                f"{LOCAL_APP_URL}/api/candidates",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "full_name": "Pipeline E2E Candidate",
                    "external_id": f"E2E-{test_id.hex[:8]}",
                    "notes": "Automatically removed after pipeline validation",
                    "recording": {
                        "storage_provider": storage_provider,
                        "storage_container": storage_container,
                        "storage_path": storage_path,
                        "original_filename": "spacewalk.wav",
                        "size_bytes": len(audio.content),
                        "mime_type": "audio/wav",
                    },
                },
            )
            create_candidate.raise_for_status()
            candidate_payload = create_candidate.json()
            candidate_id = UUID(candidate_payload["id"])
            recording_id = UUID(candidate_payload["recording_id"])

            pipeline = await _wait_for_pipeline(settings, recording_id)
            panel_admin_attempt = await client.get(
                f"{LOCAL_APP_URL}/api/admin/candidates",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            admin_email = f"codex-admin-e2e-{test_id.hex[:12]}@example.com"
            admin_password = secrets.token_urlsafe(24)
            create_admin = await client.post(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users",
                headers=service_headers,
                json={
                    "email": admin_email,
                    "password": admin_password,
                    "email_confirm": True,
                    "app_metadata": {"role": "admin"},
                },
            )
            create_admin.raise_for_status()
            admin_user_id = UUID(create_admin.json()["id"])
            admin_sign_in = await client.post(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
                headers={"apikey": settings.browser_publishable_key},
                json={"email": admin_email, "password": admin_password},
            )
            admin_sign_in.raise_for_status()
            admin_token = admin_sign_in.json()["access_token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}
            overall_score = float(pipeline["overall_score"])
            if overall_score >= 8:
                score_band = "8_to_10"
            elif overall_score >= 6:
                score_band = "6_to_7_99"
            elif overall_score >= 4:
                score_band = "4_to_5_99"
            else:
                score_band = "0_to_3_99"

            admin_list = await client.get(
                f"{LOCAL_APP_URL}/api/admin/candidates",
                headers=admin_headers,
                params={"search": test_id.hex[2:7], "score_band": score_band},
            )
            if admin_list.is_error:
                claims = jwt.decode(admin_token, options={"verify_signature": False})
                app_metadata = claims.get("app_metadata") or {}
                raise RuntimeError(
                    f"Admin list failed ({admin_list.status_code}): {admin_list.text[:300]}; "
                    f"token algorithm={jwt.get_unverified_header(admin_token).get('alg')}, "
                    f"top-level role={claims.get('role')}, "
                    f"application role={app_metadata.get('role')}"
                )
            admin_list.raise_for_status()
            admin_list_payload = admin_list.json()
            admin_detail = await client.get(
                f"{LOCAL_APP_URL}/api/admin/candidates/{candidate_id}",
                headers=admin_headers,
            )
            admin_detail.raise_for_status()
            admin_detail_payload = admin_detail.json()
            result = {
                "candidate_created": True,
                "recording_queued": pipeline["outbox_status"] == "dispatched",
                "transcript_saved": bool(pipeline["transcript"]),
                "evaluation_saved": pipeline["overall_score"] is not None,
                "model": pipeline["model"],
                "stage": pipeline["stage"],
                "panel_admin_access_denied": panel_admin_attempt.status_code == 403,
                "admin_list_loaded": (
                    admin_list_payload["total"] == 1
                    and admin_list_payload["items"][0]["id"] == str(candidate_id)
                    and admin_list_payload["metrics"]["candidates"] >= 1
                ),
                "admin_detail_loaded": (
                    admin_detail_payload["transcript"]["text"] == pipeline["transcript"]
                    and len(admin_detail_payload["evaluation"]["scores"]) == 4
                    and admin_detail_payload["evaluation"]["model"] == "claude-sonnet-4-6"
                    and bool(admin_detail_payload["events"])
                ),
            }
        finally:
            if candidate_id is not None:
                await _delete_candidate(settings, candidate_id)
                cleanup_checks["candidate"] = True

            if storage_provider == "azure" and user_id is not None:
                delete_object = await client.request(
                    "DELETE",
                    f"{LOCAL_APP_URL}/api/recordings/upload",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={
                        "storage_provider": storage_provider,
                        "storage_container": storage_container,
                        "storage_path": storage_path,
                    },
                )
            else:
                delete_object = await client.delete(
                    f"{settings.supabase_url.rstrip('/')}/storage/v1/object/"
                    f"{storage_container}/{quote(storage_path, safe='/')}",
                    headers=service_headers,
                )
            cleanup_checks["recording"] = delete_object.status_code in {200, 204, 404}

            if user_id is not None:
                delete_user = await client.delete(
                    f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}",
                    headers=service_headers,
                )
                cleanup_checks["user"] = delete_user.status_code in {200, 404}

            if admin_user_id is not None:
                delete_admin = await client.delete(
                    f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{admin_user_id}",
                    headers=service_headers,
                )
                cleanup_checks["admin_user"] = delete_admin.status_code in {200, 404}

            if created_panel:
                await _delete_panel(settings, panel_id)
                cleanup_checks["panel"] = True

    checks = {
        **result,
        "claude_sonnet_4_6": result.get("model") == "claude-sonnet-4-6",
        "cleanup": bool(cleanup_checks) and all(cleanup_checks.values()),
    }
    ok = all(
        checks.get(name) is expected
        for name, expected in {
            "candidate_created": True,
            "recording_queued": True,
            "transcript_saved": True,
            "evaluation_saved": True,
            "panel_admin_access_denied": True,
            "admin_list_loaded": True,
            "admin_detail_loaded": True,
            "claude_sonnet_4_6": True,
            "cleanup": True,
        }.items()
    ) and checks.get("stage") == "completed"
    print(json.dumps({"ok": ok, "checks": checks}, indent=2, default=str))
    return 0 if ok else 1


def main() -> None:
    try:
        raise SystemExit(asyncio.run(run()))
    except Exception as exc:
        settings = get_settings()
        detail = str(exc)
        for secret in (
            settings.database_url,
            settings.supabase_service_role_key,
            settings.browser_publishable_key,
        ):
            if secret:
                detail = detail.replace(secret, "<redacted>")
        print(json.dumps({"ok": False, "error": type(exc).__name__, "detail": detail}))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
