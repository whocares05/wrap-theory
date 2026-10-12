from fastapi import APIRouter

from app.api.routes import (
    admin_catalog,
    admin_operations,
    admin_orders,
    dashboard,
    events,
    public,
    reports,
    staff,
    webhooks,
)

api_router = APIRouter(prefix="/v1")
api_router.include_router(public.router)
api_router.include_router(dashboard.router)
api_router.include_router(admin_orders.router)
api_router.include_router(admin_catalog.router)
api_router.include_router(admin_operations.router)
api_router.include_router(staff.router)
api_router.include_router(reports.router)
api_router.include_router(events.router)
api_router.include_router(webhooks.router)
