import httpx

from app.core.config import settings
from app.providers.notifications import NotificationMessage


class SendGridNotificationProvider:
    provider_key = "sendgrid"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def send(self, message: NotificationMessage) -> str:
        if not settings.sendgrid_api_key or not settings.sendgrid_from_email:
            raise RuntimeError("SendGrid is not configured")
        payload = {
            "personalizations": [{"to": [{"email": message.destination}]}],
            "from": {"email": settings.sendgrid_from_email},
            "subject": message.title,
            "content": [{"type": "text/plain", "value": message.body}],
        }
        async with httpx.AsyncClient(timeout=10, transport=self.transport) as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
                json=payload,
            )
        if response.status_code not in {200, 202}:
            raise RuntimeError("SendGrid rejected the notification")
        return response.headers.get("X-Message-Id", "")
