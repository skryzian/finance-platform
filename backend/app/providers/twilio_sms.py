import httpx

from app.core.config import settings
from app.providers.notifications import NotificationMessage


class TwilioSMSProvider:
    provider_key = "twilio"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def send(self, message: NotificationMessage) -> str:
        if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.twilio_from_number:
            raise RuntimeError("Twilio SMS is not configured")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
        async with httpx.AsyncClient(timeout=10, transport=self.transport) as client:
            response = await client.post(
                url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                data={"From": settings.twilio_from_number, "To": message.destination, "Body": message.body},
            )
        if response.status_code not in {200, 201}:
            raise RuntimeError("Twilio rejected the notification")
        receipt = response.json().get("sid")
        if not isinstance(receipt, str) or not receipt:
            raise RuntimeError("Twilio returned no message receipt")
        return receipt
