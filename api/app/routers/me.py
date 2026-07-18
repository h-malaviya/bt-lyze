from fastapi import APIRouter

from api.app.auth.dependencies import CurrentUserDependency
from api.app.schemas.auth import MeResponse

router = APIRouter(tags=["session"])


@router.get("/me", response_model=MeResponse)
async def me(current_user: CurrentUserDependency) -> MeResponse:
    return MeResponse(user=current_user)
