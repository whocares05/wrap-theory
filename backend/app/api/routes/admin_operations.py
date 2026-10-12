import uuid
from math import ceil
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select

from app.api.dependencies import AdminDep, SessionDep, SettingsDep, StaffDep
from app.core.errors import bad_request, not_found
from app.models.entities import (
    AuditLog,
    Campaign,
    CampaignStatus,
    Coupon,
    Customer,
    Notification,
    NotificationStatus,
    StoreSettings,
    TeamTask,
)
from app.schemas.admin import CampaignInput, CouponInput, StorePatch, TaskInput, TaskPatch
from app.services.audit import record_audit

router = APIRouter(prefix="/admin", tags=["Staff · Operations"])


def model_values(model: object, fields: list[str]) -> dict[str, Any]:
    return {field: getattr(model, field) for field in fields}


@router.get("/customers")
async def customers(
    session: SessionDep,
    _: StaffDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 25,
) -> dict[str, Any]:
    total = await session.scalar(select(func.count()).select_from(Customer)) or 0
    rows = (
        await session.scalars(
            select(Customer)
            .order_by(Customer.last_order_at.desc().nullslast())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return {
        "data": [
            model_values(
                row,
                [
                    "id",
                    "name",
                    "phone",
                    "email",
                    "marketing_consent",
                    "order_count",
                    "lifetime_value",
                    "last_order_at",
                ],
            )
            for row in rows
        ],
        "meta": {"page": page, "pageSize": page_size, "total": total, "pages": ceil(total / page_size)},
    }


@router.get("/coupons")
async def coupons(session: SessionDep, _: StaffDep) -> list[dict[str, Any]]:
    fields = [
        "id",
        "code",
        "description",
        "type",
        "value",
        "minimum_subtotal",
        "maximum_discount",
        "usage_limit",
        "usage_count",
        "starts_at",
        "ends_at",
        "is_active",
    ]
    return [
        model_values(row, fields)
        for row in (await session.scalars(select(Coupon).order_by(Coupon.created_at.desc()))).all()
    ]


@router.post("/coupons", status_code=201)
async def create_coupon(
    payload: CouponInput, request: Request, session: SessionDep, staff: StaffDep
) -> dict[str, Any]:
    if payload.type.value == "percentage" and payload.value > 10_000:
        raise bad_request("Percentage discount cannot exceed 100%")
    coupon = Coupon(**payload.model_dump(), code=payload.code.upper())
    session.add(coupon)
    await session.flush()
    record_audit(
        session, request, staff, "coupon.created", "coupon", str(coupon.id), after={"code": coupon.code}
    )
    await session.commit()
    return {"id": coupon.id, "code": coupon.code}


@router.get("/campaigns")
async def campaigns(session: SessionDep, _: StaffDep) -> list[dict[str, Any]]:
    fields = [
        "id",
        "name",
        "message",
        "channel",
        "audience",
        "status",
        "scheduled_at",
        "sent_at",
        "created_at",
    ]
    return [
        model_values(row, fields)
        for row in (await session.scalars(select(Campaign).order_by(Campaign.created_at.desc()))).all()
    ]


@router.post("/campaigns", status_code=201)
async def create_campaign(
    payload: CampaignInput, request: Request, session: SessionDep, staff: StaffDep
) -> dict[str, Any]:
    campaign = Campaign(
        name=payload.name,
        message=payload.message,
        audience=payload.audience,
        scheduled_at=payload.scheduled_at,
        status=CampaignStatus.SCHEDULED if payload.scheduled_at else CampaignStatus.DRAFT,
        created_by=staff.user_id,
    )
    session.add(campaign)
    await session.flush()
    record_audit(
        session,
        request,
        staff,
        "campaign.created",
        "campaign",
        str(campaign.id),
        after={"name": campaign.name},
    )
    await session.commit()
    return {"id": campaign.id, "status": campaign.status}


@router.post("/campaigns/{campaign_id}/send")
async def send_campaign(
    campaign_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    if not settings.whatsapp_enabled:
        raise bad_request("WhatsApp is not enabled. The campaign remains safely in draft.")
    campaign = await session.scalar(select(Campaign).where(Campaign.id == campaign_id).with_for_update())
    if campaign is None:
        raise not_found("Campaign not found")
    if campaign.status not in {CampaignStatus.DRAFT, CampaignStatus.SCHEDULED}:
        raise bad_request("Campaign cannot be sent from its current state")
    recipients = (
        await session.scalars(
            select(Customer).where(Customer.marketing_consent.is_(True)).order_by(Customer.id)
        )
    ).all()
    for customer in recipients:
        session.add(
            Notification(
                campaign_id=campaign.id,
                channel="whatsapp",
                recipient=customer.phone,
                template=settings.whatsapp_marketing_template,
                payload={"customerName": customer.name, "message": campaign.message},
                status=NotificationStatus.PENDING,
            )
        )
    campaign.status = CampaignStatus.SENDING
    record_audit(
        session,
        request,
        admin,
        "campaign.queued",
        "campaign",
        str(campaign.id),
        after={"recipients": len(recipients)},
    )
    await session.commit()
    return {"id": campaign.id, "status": campaign.status, "recipients": len(recipients)}


@router.get("/tasks")
async def tasks(session: SessionDep, _: StaffDep) -> list[dict[str, Any]]:
    fields = ["id", "title", "description", "status", "assigned_to", "due_at", "created_by", "created_at"]
    return [
        model_values(row, fields)
        for row in (await session.scalars(select(TeamTask).order_by(TeamTask.created_at.desc()))).all()
    ]


@router.post("/tasks", status_code=201)
async def create_task(
    payload: TaskInput, request: Request, session: SessionDep, staff: StaffDep
) -> dict[str, Any]:
    task = TeamTask(**payload.model_dump(), created_by=staff.user_id)
    session.add(task)
    await session.flush()
    record_audit(session, request, staff, "task.created", "task", str(task.id), after={"title": task.title})
    await session.commit()
    return {"id": task.id, "status": task.status}


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: uuid.UUID, payload: TaskPatch, request: Request, session: SessionDep, staff: StaffDep
) -> dict[str, Any]:
    task = await session.scalar(select(TeamTask).where(TeamTask.id == task_id).with_for_update())
    if task is None:
        raise not_found("Task not found")
    before = {"title": task.title, "status": task.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    record_audit(
        session,
        request,
        staff,
        "task.updated",
        "task",
        str(task.id),
        before=before,
        after={"title": task.title, "status": task.status},
    )
    await session.commit()
    return {"id": task.id, "status": task.status}


@router.get("/store")
async def get_store(session: SessionDep, _: AdminDep) -> dict[str, Any]:
    store = await session.scalar(select(StoreSettings).limit(1))
    if store is None:
        raise not_found("Store settings not found")
    return model_values(
        store,
        [
            "id",
            "name",
            "phone",
            "email",
            "address",
            "city",
            "timezone",
            "currency",
            "tax_rate_bps",
            "default_delivery_fee",
            "minimum_order",
            "free_delivery_threshold",
            "accepts_delivery",
            "accepts_pickup",
            "orders_paused",
            "opening_hours",
        ],
    )


@router.patch("/store")
async def update_store(
    payload: StorePatch, request: Request, session: SessionDep, admin: AdminDep
) -> dict[str, Any]:
    store = await session.scalar(select(StoreSettings).limit(1).with_for_update())
    if store is None:
        raise not_found("Store settings not found")
    changes = payload.model_dump(exclude_unset=True)
    before = {field: getattr(store, field) for field in changes}
    for field, value in changes.items():
        setattr(store, field, value)
    record_audit(
        session, request, admin, "store.updated", "store", str(store.id), before=before, after=changes
    )
    await session.commit()
    return {"id": store.id, **changes}


@router.get("/audit-logs")
async def audit_logs(
    session: SessionDep,
    _: AdminDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[dict[str, Any]]:
    fields = [
        "id",
        "actor_id",
        "actor_email",
        "action",
        "entity_type",
        "entity_id",
        "before",
        "after",
        "ip_address",
        "request_id",
        "created_at",
    ]
    return [
        model_values(row, fields)
        for row in (
            await session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
        ).all()
    ]
