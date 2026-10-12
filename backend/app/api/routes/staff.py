import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.dependencies import AdminDep, SessionDep, StaffDep
from app.core.errors import bad_request, not_found
from app.models.entities import StaffProfile
from app.schemas.admin import StaffInviteInput, StaffResponse, UpdateStaffInput
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/staff", tags=["Staff · Team"])


@router.get("/me", response_model=StaffResponse)
async def me(staff: StaffDep, session: SessionDep) -> StaffProfile:
    profile = await session.scalar(select(StaffProfile).where(StaffProfile.user_id == staff.user_id))
    assert profile is not None
    return profile


@router.get("", response_model=list[StaffResponse])
async def list_staff(_: AdminDep, session: SessionDep) -> list[StaffProfile]:
    return list((await session.scalars(select(StaffProfile).order_by(StaffProfile.display_name))).all())


@router.post("/invitations", status_code=201)
async def invite_staff(
    payload: StaffInviteInput,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> dict[str, Any]:
    settings = request.app.state.settings
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{str(settings.supabase_url).rstrip('/')}/auth/v1/invite",
            params={"redirect_to": f"{str(settings.frontend_app_url).rstrip('/')}/auth/callback"},
            headers={
                "apikey": settings.supabase_service_role_key.get_secret_value(),
                "Authorization": f"Bearer {settings.supabase_service_role_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json={"email": str(payload.email)},
        )
    if response.status_code >= 400:
        raise bad_request("Supabase could not invite this staff member", response.json())
    user_id = uuid.UUID(response.json()["id"])
    profile = StaffProfile(
        user_id=user_id,
        email=str(payload.email).lower(),
        display_name=payload.display_name,
        role=payload.role,
    )
    session.add(profile)
    record_audit(
        session,
        request,
        admin,
        "staff.invited",
        "staff",
        str(user_id),
        after={"email": profile.email, "role": profile.role},
    )
    await session.commit()
    return {"userId": user_id, "email": profile.email, "role": profile.role}


@router.patch("/{user_id}")
async def update_staff(
    user_id: uuid.UUID,
    payload: UpdateStaffInput,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> dict[str, Any]:
    profile = await session.scalar(
        select(StaffProfile).where(StaffProfile.user_id == user_id).with_for_update()
    )
    if profile is None:
        raise not_found("Staff member not found")
    if profile.user_id == admin.user_id and payload.is_active is False:
        raise bad_request("You cannot deactivate your own account")
    before = {"role": profile.role, "isActive": profile.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    record_audit(
        session,
        request,
        admin,
        "staff.updated",
        "staff",
        str(profile.user_id),
        before=before,
        after={"role": profile.role, "isActive": profile.is_active},
    )
    await session.commit()
    return {"userId": profile.user_id, "role": profile.role, "isActive": profile.is_active}
