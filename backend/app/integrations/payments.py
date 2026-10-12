from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    provider_reference: str
    redirect_url: str


class SafepayClient:
    """Activation boundary for Safepay.

    COD is the only enabled production method. The adapter intentionally refuses
    traffic until merchant onboarding, exact API credentials, and webhook signing
    requirements have been confirmed against the merchant's Safepay account.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create_checkout(self, order_number: str, amount: int) -> CheckoutSession:
        del order_number, amount
        if not self.settings.safepay_enabled:
            raise RuntimeError("Safepay is disabled")
        raise NotImplementedError(
            "Complete merchant-specific Safepay onboarding before enabling online payments"
        )
