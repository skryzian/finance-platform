from typing import Protocol


class NotificationMessage(Protocol):
    title: str
    body: str
    destination: str


class NotificationProvider(Protocol):
    provider_key: str

    async def send(self, message: NotificationMessage) -> str:
        """Send through one configured channel and return its provider receipt ID."""
        ...
