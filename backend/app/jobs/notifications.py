import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy import select

from app.core.config import Settings
from app.db.session import Database
from app.integrations.whatsapp import WhatsAppClient
from app.models.entities import Notification, NotificationStatus

logger = structlog.get_logger()


class NotificationWorker:
    def __init__(self, database: Database, settings: Settings, http: httpx.AsyncClient) -> None:
        self.database = database
        self.settings = settings
        self.whatsapp = WhatsAppClient(settings, http)
        self._stopping = asyncio.Event()

    def stop(self) -> None:
        self._stopping.set()

    async def run(self) -> None:
        while not self._stopping.is_set():
            try:
                processed = await self.process_batch()
            except Exception:
                logger.exception("notification_worker_failed")
                processed = 0
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stopping.wait(), timeout=1 if processed else 5)

    async def process_batch(self) -> int:
        async with self.database.sessions() as session, session.begin():
            rows = list(
                (
                    await session.scalars(
                        select(Notification)
                        .where(
                            Notification.status.in_([NotificationStatus.PENDING, NotificationStatus.FAILED]),
                            Notification.next_attempt_at <= datetime.now(UTC),
                            Notification.attempts < 5,
                        )
                        .order_by(Notification.created_at)
                        .limit(10)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            for notification in rows:
                notification.status = NotificationStatus.PROCESSING
                notification.attempts += 1
            await session.flush()
            for notification in rows:
                try:
                    if notification.channel != "whatsapp":
                        raise RuntimeError(f"Unsupported notification channel: {notification.channel}")
                    result = await self.whatsapp.send_template(
                        notification.recipient, notification.template, notification.payload
                    )
                    notification.status = NotificationStatus.SENT
                    notification.provider_reference = result.provider_reference
                    notification.sent_at = datetime.now(UTC)
                    notification.last_error = None
                except Exception as error:
                    notification.status = NotificationStatus.FAILED
                    notification.last_error = str(error)[:1000]
                    notification.next_attempt_at = datetime.now(UTC) + timedelta(
                        minutes=2**notification.attempts
                    )
            return len(rows)
