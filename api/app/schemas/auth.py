from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class UserRole(StrEnum):
    ADMIN = "admin"
    PANEL = "panel"


class CurrentUser(BaseModel):
    id: UUID
    email: str | None = None
    role: UserRole
    panel_id: UUID | None = None
    full_name: str | None = None


class MeResponse(BaseModel):
    user: CurrentUser
