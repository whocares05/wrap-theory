from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import StaffContext
from app.models.entities import AuditLog


def record_audit(
    session: AsyncSession,
    request: Request,
    staff: StaffContext,
    action: str,
    entity_type: str,
    entity_id: str | None,
    *,
    before: Any = None,
    after: Any = None,
) -> None:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    session.add(
        AuditLog(
            actor_id=staff.user_id,
            actor_email=staff.email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            ip_address=forwarded_for or (request.client.host if request.client else None),
            user_agent=request.headers.get("user-agent"),
            request_id=getattr(request.state, "request_id", None),
        )
    )
