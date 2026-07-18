from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials

from api.app.auth.dependencies import get_current_user
from api.app.config import Settings
from api.app.schemas.auth import UserRole


@pytest.mark.asyncio
async def test_app_metadata_role_takes_precedence_over_postgres_role() -> None:
    secret = "test-secret-long-enough-for-unit-tests"
    token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "aud": "authenticated",
            "role": "authenticated",
            "email": "admin@example.com",
            "app_metadata": {"role": "admin"},
        },
        secret,
        algorithm="HS256",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    settings = Settings(supabase_url="", supabase_jwt_secret=secret)

    user = await get_current_user(credentials, settings)

    assert user.id == UUID("00000000-0000-0000-0000-000000000001")
    assert user.role is UserRole.ADMIN


@pytest.mark.asyncio
async def test_access_token_allows_small_issuer_clock_skew() -> None:
    secret = "test-secret-long-enough-for-unit-tests"
    token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000002",
            "aud": "authenticated",
            "iat": datetime.now(UTC) + timedelta(seconds=10),
            "app_metadata": {"role": "admin"},
        },
        secret,
        algorithm="HS256",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    settings = Settings(supabase_url="", supabase_jwt_secret=secret)

    user = await get_current_user(credentials, settings)

    assert user.id == UUID("00000000-0000-0000-0000-000000000002")
    assert user.role is UserRole.ADMIN
