import base64
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings


class MpesaProviderError(RuntimeError):
    pass


class MpesaDarajaProvider:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = (
            "https://sandbox.safaricom.co.ke"
            if settings.mpesa_environment == "sandbox"
            else "https://api.safaricom.co.ke"
        )
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=15,
            transport=transport,
        )

    async def access_token(self) -> str:
        response = await self.client.get(
            "/oauth/v1/generate",
            params={"grant_type": "client_credentials"},
            auth=(settings.mpesa_consumer_key, settings.mpesa_consumer_secret),
        )
        if response.status_code != 200:
            raise MpesaProviderError("Daraja authentication failed")
        payload = response.json()
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise MpesaProviderError("Daraja returned no access token")
        return token

    async def initiate_stk_push(
        self,
        *,
        phone_number: str,
        amount: int,
        account_reference: str,
        description: str,
    ) -> dict:
        token = await self.access_token()
        timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{settings.mpesa_shortcode}{settings.mpesa_passkey}{timestamp}".encode("utf-8")
        ).decode("ascii")
        callback_url = (
            f"{settings.mpesa_callback_base_url.rstrip('/')}/api/integrations/mpesa/stk/callback"
            f"?token={settings.mpesa_callback_token}"
        )
        response = await self.client.post(
            "/mpesa/stkpush/v1/processrequest",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "BusinessShortCode": settings.mpesa_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": settings.mpesa_transaction_type,
                "Amount": amount,
                "PartyA": phone_number,
                "PartyB": settings.mpesa_shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": callback_url,
                "AccountReference": account_reference,
                "TransactionDesc": description[:100],
            },
        )
        if response.status_code != 200:
            raise MpesaProviderError("Daraja rejected the STK Push request")
        payload = response.json()
        if not isinstance(payload, dict):
            raise MpesaProviderError("Daraja returned an invalid STK Push response")
        if payload.get("ResponseCode") not in {"0", 0}:
            raise MpesaProviderError("Daraja did not accept the STK Push request")
        return payload

    async def register_c2b_urls(self) -> dict:
        token = await self.access_token()
        base = settings.mpesa_callback_base_url.rstrip("/")
        suffix = f"?token={settings.mpesa_callback_token}"
        response = await self.client.post(
            "/mpesa/c2b/v1/registerurl",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "ShortCode": settings.mpesa_shortcode,
                "ResponseType": "Completed",
                "ConfirmationURL": f"{base}/api/integrations/mpesa/c2b/confirmation{suffix}",
                "ValidationURL": f"{base}/api/integrations/mpesa/c2b/validation{suffix}",
            },
        )
        if response.status_code != 200:
            raise MpesaProviderError("Daraja rejected C2B callback registration")
        payload = response.json()
        if not isinstance(payload, dict):
            raise MpesaProviderError("Daraja returned an invalid callback registration response")
        if payload.get("ResponseDescription") not in {None, "Success"}:
            raise MpesaProviderError("Daraja did not confirm C2B callback registration")
        return payload

    async def aclose(self) -> None:
        await self.client.aclose()
