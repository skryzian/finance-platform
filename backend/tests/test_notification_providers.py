import asyncio
from dataclasses import dataclass
import json

import httpx

from app.providers.expo_push import ExpoPushProvider
from app.providers.mpesa_daraja import MpesaDarajaProvider
from app.providers.sendgrid import SendGridNotificationProvider
from app.providers.twilio_sms import TwilioSMSProvider


@dataclass(frozen=True)
class MessageFixture:
    title: str
    body: str
    destination: str


def test_sendgrid_sends_mail_and_returns_provider_receipt(monkeypatch):
    monkeypatch.setattr("app.providers.sendgrid.settings.sendgrid_api_key", "test-sendgrid-key")
    monkeypatch.setattr("app.providers.sendgrid.settings.sendgrid_from_email", "alerts@example.com")
    captured = []

    def handler(request):
        captured.append(request)
        assert request.headers["Authorization"] == "Bearer test-sendgrid-key"
        assert request.url.path == "/v3/mail/send"
        return httpx.Response(202, headers={"X-Message-Id": "mail-123"})

    provider = SendGridNotificationProvider(transport=httpx.MockTransport(handler))
    message = MessageFixture(title="Test", body="Generic body", destination="user@example.com")
    assert asyncio.run(provider.send(message)) == "mail-123"
    assert captured[0].content


def test_twilio_sends_sms_with_basic_auth(monkeypatch):
    monkeypatch.setattr("app.providers.twilio_sms.settings.twilio_account_sid", "AC123")
    monkeypatch.setattr("app.providers.twilio_sms.settings.twilio_auth_token", "twilio-test-token")
    monkeypatch.setattr("app.providers.twilio_sms.settings.twilio_from_number", "+254700000000")

    def handler(request):
        assert request.headers["Authorization"].startswith("Basic ")
        assert request.url.path.endswith("/Accounts/AC123/Messages.json")
        assert b"To=%2B254700000001" in request.read()
        return httpx.Response(201, json={"sid": "SM123"})

    provider = TwilioSMSProvider(transport=httpx.MockTransport(handler))
    message = MessageFixture(title="Test", body="Generic body", destination="+254700000001")
    assert asyncio.run(provider.send(message)) == "SM123"


def test_expo_push_sends_token_and_validates_ticket(monkeypatch):
    monkeypatch.setattr("app.providers.expo_push.settings.expo_access_token", "expo-access-token")

    def handler(request):
        assert request.headers["Authorization"] == "Bearer expo-access-token"
        payload = request.read().decode("utf-8")
        assert "ExponentPushToken[test-device]" in payload
        return httpx.Response(200, json={"data": {"status": "ok", "id": "ticket-123"}})

    provider = ExpoPushProvider(transport=httpx.MockTransport(handler))
    message = MessageFixture(
        title="Test",
        body="Generic body",
        destination="ExponentPushToken[test-device]",
    )
    assert asyncio.run(provider.send(message)) == "ticket-123"


def test_daraja_oauth_and_stk_push_use_expected_headers_and_fields(monkeypatch):
    monkeypatch.setattr("app.providers.mpesa_daraja.settings.mpesa_environment", "sandbox")
    monkeypatch.setattr("app.providers.mpesa_daraja.settings.mpesa_consumer_key", "test-key")
    monkeypatch.setattr("app.providers.mpesa_daraja.settings.mpesa_consumer_secret", "test-secret")
    monkeypatch.setattr("app.providers.mpesa_daraja.settings.mpesa_shortcode", "174379")
    monkeypatch.setattr("app.providers.mpesa_daraja.settings.mpesa_passkey", "test-passkey")
    monkeypatch.setattr("app.providers.mpesa_daraja.settings.mpesa_transaction_type", "CustomerPayBillOnline")
    monkeypatch.setattr("app.providers.mpesa_daraja.settings.mpesa_callback_base_url", "https://finance.example.com")
    monkeypatch.setattr("app.providers.mpesa_daraja.settings.mpesa_callback_token", "callback-token")
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/oauth/v1/generate":
            assert request.headers["Authorization"].startswith("Basic ")
            return httpx.Response(200, json={"access_token": "provider-token"})
        assert request.headers["Authorization"] == "Bearer provider-token"
        body = json.loads(request.read().decode("utf-8"))
        assert body["BusinessShortCode"] == "174379"
        assert body["Amount"] == 10
        assert "callback-token" in body["CallBackURL"]
        return httpx.Response(200, json={
            "ResponseCode": "0",
            "MerchantRequestID": "merchant-1",
            "CheckoutRequestID": "checkout-1",
        })

    provider = MpesaDarajaProvider(transport=httpx.MockTransport(handler))

    async def run():
        try:
            return await provider.initiate_stk_push(
                phone_number="254712345678",
                amount=10,
                account_reference="FP0000000001",
                description="Purchase",
            )
        finally:
            await provider.aclose()

    result = asyncio.run(run())
    assert result["CheckoutRequestID"] == "checkout-1"
    assert len(seen) == 2
