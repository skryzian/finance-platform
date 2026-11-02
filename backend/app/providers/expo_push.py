import httpx

from app.core.config import settings
from app.providers.notifications import NotificationMessage


class ExpoPushProvider:
    provider_key = "expo"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def send(self, message: NotificationMessage) -> str:
        payload = {
            "to": message.destination,
            "title": message.title,
            "body": message.body,
            "sound": "default",
        }
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if settings.expo_access_token:
            headers["Authorization"] = f"Bearer {settings.expo_access_token}"
        async with httpx.AsyncClient(timeout=10, transport=self.transport) as client:
            response = await client.post("https://exp.host/--/api/v2/push/send", headers=headers, json=payload)
        if response.status_code != 200:
            raise RuntimeError("Expo Push Service rejected the notification")
        body = response.json()
        data = body.get("data")
        if not isinstance(data, dict) or data.get("status") != "ok":
            raise RuntimeError("Expo Push Service returned a delivery error")
        receipt = data.get("id")
        if not isinstance(receipt, str) or not receipt:
            raise RuntimeError("Expo Push Service returned no ticket ID")
        return receipt
