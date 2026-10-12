from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    provider_reference: str


class WhatsAppClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http = http

    async def send_template(self, recipient: str, template: str, payload: dict[str, Any]) -> DeliveryResult:
        if not self.settings.whatsapp_enabled:
            raise RuntimeError("WhatsApp is disabled")
        assert self.settings.whatsapp_phone_number_id
        assert self.settings.whatsapp_access_token
        parameter_keys: tuple[str, ...] = (
            ("customerName", "message") if "message" in payload else ("customerName", "orderNumber", "total")
        )
        parameters = [{"type": "text", "text": str(payload[key])} for key in parameter_keys if key in payload]
        response = await self.http.post(
            f"https://graph.facebook.com/{self.settings.whatsapp_api_version}/"
            f"{self.settings.whatsapp_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {self.settings.whatsapp_access_token.get_secret_value()}"},
            json={
                "messaging_product": "whatsapp",
                "to": recipient.lstrip("+"),
                "type": "template",
                "template": {
                    "name": template,
                    "language": {"code": self.settings.whatsapp_template_language},
                    "components": [{"type": "body", "parameters": parameters}],
                },
            },
        )
        response.raise_for_status()
        body = response.json()
        return DeliveryResult(provider_reference=str(body["messages"][0]["id"]))
