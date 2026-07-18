import asyncio
from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.app.config import Settings, get_settings
from api.app.schemas.auth import CurrentUser, UserRole

bearer_scheme = HTTPBearer(auto_error=False)
AUTH_CLOCK_SKEW_SECONDS = 30


@lru_cache(maxsize=4)
def _get_jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=600)


def _claim(payload: dict[str, Any], key: str) -> Any:
    app_metadata = payload.get("app_metadata") or {}
    user_metadata = payload.get("user_metadata") or {}
    return app_metadata.get(key) or payload.get(key) or user_metadata.get(key)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")

    try:
        token = credentials.credentials
        algorithm = jwt.get_unverified_header(token).get("alg")
        issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1" if settings.supabase_url else None
        decode_kwargs: dict[str, Any] = {
            "algorithms": [algorithm],
            "audience": "authenticated",
        }
        if issuer:
            decode_kwargs["issuer"] = issuer

        if algorithm == "HS256" and settings.supabase_jwt_secret:
            signing_key: str | Any = settings.supabase_jwt_secret
        elif algorithm in {"ES256", "RS256"} and settings.supabase_url:
            jwks_url = f"{issuer}/.well-known/jwks.json"
            signing_key = await asyncio.to_thread(
                _get_jwks_client(jwks_url).get_signing_key_from_jwt,
                token,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication signing keys are not configured",
            )

        payload = jwt.decode(
            token,
            signing_key,
            leeway=AUTH_CLOCK_SKEW_SECONDS,
            **decode_kwargs,
        )
        role = UserRole(_claim(payload, "role"))
        panel_id_claim = _claim(payload, "panel_id")
        return CurrentUser(
            id=UUID(payload["sub"]),
            email=payload.get("email"),
            role=role,
            panel_id=UUID(panel_id_claim) if panel_id_claim else None,
            full_name=_claim(payload, "full_name"),
        )
    except HTTPException:
        raise
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc


CurrentUserDependency = Annotated[CurrentUser, Depends(get_current_user)]
