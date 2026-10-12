from fastapi import APIRouter, Request

from app.api.dependencies import SettingsDep
from app.core.errors import AppError

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/safepay", include_in_schema=False)
async def safepay_webhook(request: Request, settings: SettingsDep) -> dict[str, bool]:
    del request
    if not settings.safepay_enabled:
        raise AppError(503, "INTEGRATION_DISABLED", "Safepay is not enabled")
    raise AppError(
        501,
        "PROVIDER_ONBOARDING_REQUIRED",
        "Webhook verification must be completed against the merchant's Safepay account before activation",
    )
