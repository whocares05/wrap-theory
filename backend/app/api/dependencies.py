import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import forbidden, unauthorized
from app.core.security import verify_supabase_token
from app.db.session import Database
from app.models.entities import StaffProfile, StaffRole

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class StaffContext:
    user_id: uuid.UUID
    email: str
    display_name: str
    role: StaffRole


def get_settings_from_request(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database: Database = request.app.state.database
    async for session in database.session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_from_request)]


async def require_staff(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: SettingsDep,
    session: SessionDep,
) -> StaffContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    identity = await verify_supabase_token(credentials.credentials, settings)
    profile = await session.scalar(select(StaffProfile).where(StaffProfile.user_id == identity.user_id))
    if profile is None or not profile.is_active:
        raise forbidden("This account does not have active staff access")
    await session.execute(
        update(StaffProfile)
        .where(StaffProfile.user_id == profile.user_id)
        .values(last_seen_at=datetime.now(UTC))
    )
    await session.commit()
    return StaffContext(profile.user_id, profile.email, profile.display_name, profile.role)


StaffDep = Annotated[StaffContext, Depends(require_staff)]


async def require_admin(staff: StaffDep) -> StaffContext:
    if staff.role != StaffRole.ADMIN:
        raise forbidden("Administrator access is required")
    return staff


AdminDep = Annotated[StaffContext, Depends(require_admin)]
