from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.app.auth.dependencies import CurrentUserDependency
from api.app.config import Settings, get_settings
from api.app.schemas.auth import UserRole
from api.app.services.dependency_health import check_runtime_dependencies

router = APIRouter(tags=["health"])


@router.get("/health/dependencies")
async def dependency_health(
    current_user: CurrentUserDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    if current_user.role is not UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    dependencies = await check_runtime_dependencies(settings)
    return {
        "status": "ok" if all(item["ok"] for item in dependencies) else "degraded",
        "dependencies": dependencies,
    }
