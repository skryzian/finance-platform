import asyncio
from datetime import datetime, timezone

from app.db.database import SessionLocal
from app.models.integrations import Notification, NotificationDelivery
from app.models.finance import Transaction
from app.services.notifications import dispatch_delivery, enqueue_notification


def create_user(client, email):
    registration = client.post(
        "/auth/register",
        json={
            "first_name": "Integration",
            "last_name": "Tester",
            "email": email,
            "password": "StrongPassword123!",
            "country": "KE",
        },
    )
    assert registration.status_code == 201, registration.text
    login = client.post("/auth/login", json={"email": email, "password": "StrongPassword123!"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_ledger_refs(client, token):
    account = client.post(
        "/api/finance/accounts",
        headers=headers(token),
        json={
            "name": "M-Pesa wallet",
            "account_type": "MOBILE_MONEY",
            "currency_code": "KES",
            "opening_balance": "1000",
        },
    )
    assert account.status_code == 201, account.text
    income = client.post(
        "/api/finance/categories",
        headers=headers(token),
        json={"name": "Cash received", "category_type": "INCOME"},
    )
    assert income.status_code == 201, income.text
    expense = client.post(
        "/api/finance/categories",
        headers=headers(token),
        json={"name": "Purchases", "category_type": "EXPENSE"},
    )
    assert expense.status_code == 201, expense.text
    return account.json()["id"], income.json()["id"], expense.json()["id"]


class FakeDaraja:
    calls = 0

    async def initiate_stk_push(self, **kwargs):
        type(self).calls += 1
        assert kwargs["phone_number"] == "254712345678"
        assert kwargs["amount"] == 10
        return {
            "ResponseCode": "0",
            "MerchantRequestID": "merchant-1",
            "CheckoutRequestID": "checkout-1",
            "CustomerMessage": "Prompt sent",
        }

    async def aclose(self):
        return None


def configure_mpesa(monkeypatch):
    monkeypatch.setattr("app.api.routes.mpesa.settings.mpesa_enabled", True)
    monkeypatch.setattr("app.api.routes.mpesa.settings.mpesa_environment", "sandbox")
    monkeypatch.setattr("app.api.routes.mpesa.settings.mpesa_shortcode", "174379")
    monkeypatch.setattr("app.api.routes.mpesa.settings.mpesa_callback_token", "a" * 40)


def test_notification_preferences_and_in_app_feed_are_user_scoped(client):
    first_token = create_user(client, "notify.first@example.com")
    second_token = create_user(client, "notify.second@example.com")
    first_headers = headers(first_token)
    second_headers = headers(second_token)
    first_user_id = client.get("/auth/me", headers=first_headers).json()["id"]

    preferences = client.get("/api/notifications/preferences", headers=first_headers)
    assert preferences.status_code == 200
    assert preferences.json()["email_enabled"] is False
    assert preferences.json()["budget_alerts_enabled"] is True
    assert client.put(
        "/api/notifications/preferences",
        headers=first_headers,
        json={
            "email_enabled": False,
            "sms_enabled": True,
            "push_enabled": False,
            "budget_alerts_enabled": True,
            "mpesa_events_enabled": True,
            "sync_events_enabled": True,
            "security_events_enabled": True,
        },
    ).status_code == 422

    with SessionLocal() as db:
        notification = enqueue_notification(
            db,
            user_id=first_user_id,
            event_type="SECURITY",
            event_key="security-test",
            title="Security notice",
            body="Private test notice",
        )
        assert notification is not None
        notification_id = notification.id

    first_feed = client.get("/api/notifications", headers=first_headers)
    second_feed = client.get("/api/notifications", headers=second_headers)
    assert any(item["id"] == notification_id for item in first_feed.json())
    assert all(item["id"] != notification_id for item in second_feed.json())
    assert client.post(f"/api/notifications/{notification_id}/read", headers=second_headers).status_code == 404
    assert client.post(f"/api/notifications/{notification_id}/read", headers=first_headers).status_code == 200


def test_push_device_registration_is_private_and_revocable(client):
    first_token = create_user(client, "notify.push.first@example.com")
    second_token = create_user(client, "notify.push.second@example.com")
    first_headers = headers(first_token)
    second_headers = headers(second_token)
    payload = {"push_token": "ExponentPushToken[test-device-token]", "platform": "android"}
    registered = client.post("/api/notifications/devices", headers=first_headers, json=payload)
    assert registered.status_code == 201
    device_id = registered.json()["id"]
    assert "push_token" not in registered.json()
    assert client.post("/api/notifications/devices", headers=second_headers, json=payload).status_code == 409

    preferences = client.get("/api/notifications/preferences", headers=first_headers).json()
    preferences["push_enabled"] = True
    assert client.put("/api/notifications/preferences", headers=first_headers, json=preferences).status_code == 200
    assert client.delete(f"/api/notifications/devices/{device_id}", headers=first_headers).status_code == 204
    assert client.get("/api/notifications/preferences", headers=first_headers).json()["push_enabled"] is False
    assert client.get("/api/notifications/devices", headers=first_headers).json() == []


def test_notification_delivery_uses_generic_external_content_and_is_idempotent(client, monkeypatch):
    token = create_user(client, "notify.delivery@example.com")
    user_id = client.get("/auth/me", headers=headers(token)).json()["id"]
    pref = client.get("/api/notifications/preferences", headers=headers(token)).json()
    pref["email_enabled"] = True
    assert client.put("/api/notifications/preferences", headers=headers(token), json=pref).status_code == 200

    with SessionLocal() as db:
        notification = enqueue_notification(
            db,
            user_id=user_id,
            event_type="BUDGET",
            event_key="budget-test",
            title="Private budget details",
            body="Spent 99999 KES on a sensitive item",
        )
        duplicate = enqueue_notification(
            db,
            user_id=user_id,
            event_type="BUDGET",
            event_key="budget-test",
            title="Private budget details",
            body="duplicate",
        )
        assert notification.id == duplicate.id
        delivery_id = db.query(NotificationDelivery).one().id

    sent = []

    class FakeProvider:
        async def send(self, message):
            sent.append(message)
            return "receipt-1"

    monkeypatch.setattr("app.services.notifications._provider", lambda _: FakeProvider())
    asyncio.run(dispatch_delivery(delivery_id))

    with SessionLocal() as db:
        delivery = db.query(NotificationDelivery).one()
        assert delivery.status == "ACCEPTED"
        assert delivery.provider_receipt == "receipt-1"
        assert len(sent) == 1
        assert sent[0].title == "Finance Platform update"
        assert sent[0].body == "Sign in to Finance Platform to view this update."
        assert "Private budget" not in sent[0].title
        assert "99999" not in sent[0].body
        assert db.query(Notification).count() >= 1


def test_budget_threshold_notifications_are_deduplicated(client):
    token = create_user(client, "notify.budget@example.com")
    auth = headers(token)
    account_id, _, expense_id = create_ledger_refs(client, token)
    today = datetime.now(timezone.utc).date().isoformat()
    budget = client.post(
        "/api/finance/budgets",
        headers=auth,
        json={
            "name": "Monthly groceries",
            "category_id": expense_id,
            "amount": "100",
            "currency_code": "KES",
            "start_date": today,
            "end_date": today,
        },
    )
    assert budget.status_code == 201, budget.text
    for key, amount in (("expense-80", "80"), ("expense-20", "20")):
        response = client.post(
            "/api/finance/transactions",
            headers=auth,
            json={
                "idempotency_key": key,
                "account_id": account_id,
                "category_id": expense_id,
                "transaction_type": "EXPENSE",
                "amount": amount,
                "currency_code": "KES",
                "description": "Groceries",
                "transaction_date": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert response.status_code == 201, response.text
    notifications = client.get("/api/notifications", headers=auth).json()
    budget_alerts = [item for item in notifications if item["event_type"] == "BUDGET"]
    assert len(budget_alerts) == 2
    assert any("80%" in item["body"] for item in budget_alerts)
    assert any("100%" in item["body"] for item in budget_alerts)


def test_mpesa_c2b_callback_records_income_once_and_checks_callback_token(client, monkeypatch):
    configure_mpesa(monkeypatch)
    token = create_user(client, "mpesa.c2b@example.com")
    account_id, income_id, _ = create_ledger_refs(client, token)
    auth = headers(token)
    mapping = client.put(
        "/api/integrations/mpesa/account-mapping",
        headers=auth,
        json={"account_id": account_id, "income_category_id": income_id, "account_reference": "salary-1"},
    )
    assert mapping.status_code == 200, mapping.text
    assert mapping.json()["account_reference"] == "SALARY-1"

    callback = {
        "BusinessShortCode": "174379",
        "TransID": "QWERTY123",
        "TransAmount": "250",
        "BillRefNumber": "SALARY-1",
        "TransTime": "20261102111213",
    }
    assert client.post("/api/integrations/mpesa/c2b/validation?token=wrong", json=callback).status_code == 401
    validation = client.post(
        "/api/integrations/mpesa/c2b/validation?token=" + "a" * 40,
        json=callback,
    )
    assert validation.status_code == 200
    assert validation.json()["ResultCode"] == 0

    path = "/api/integrations/mpesa/c2b/confirmation?token=" + "a" * 40
    first = client.post(path, json=callback)
    second = client.post(path, json=callback)
    assert first.json()["ResultCode"] == 0
    assert second.json()["ResultCode"] == 0
    transactions = client.get("/api/finance/transactions", headers=auth).json()
    assert len([item for item in transactions if item["description"] == "M-Pesa payment QWERTY123"]) == 1
    assert client.get("/api/finance/accounts", headers=auth).json()[0]["current_balance"] == "1250.00000000"


def test_mpesa_stk_is_idempotent_and_posts_only_after_matching_callback(client, monkeypatch):
    configure_mpesa(monkeypatch)
    monkeypatch.setattr("app.api.routes.mpesa.MpesaDarajaProvider", FakeDaraja)
    FakeDaraja.calls = 0
    token = create_user(client, "mpesa.stk@example.com")
    account_id, _, expense_id = create_ledger_refs(client, token)
    auth = headers(token)
    payload = {
        "idempotency_key": "client-order-1",
        "account_id": account_id,
        "category_id": expense_id,
        "amount": "10",
        "phone_number": "254712345678",
        "description": "Market purchase",
    }
    first = client.post("/api/integrations/mpesa/stk-push", headers=auth, json=payload)
    duplicate = client.post("/api/integrations/mpesa/stk-push", headers=auth, json=payload)
    assert first.status_code == 202
    assert first.json()["status"] == "PENDING"
    assert duplicate.status_code == 200
    assert FakeDaraja.calls == 1
    conflict = client.post(
        "/api/integrations/mpesa/stk-push",
        headers=auth,
        json={**payload, "amount": "11"},
    )
    assert conflict.status_code == 409
    assert client.get("/api/finance/transactions", headers=auth).json() == []

    callback = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "merchant-1",
                "CheckoutRequestID": "checkout-1",
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 10},
                        {"Name": "MpesaReceiptNumber", "Value": "AB123456"},
                        {"Name": "PhoneNumber", "Value": 254712345678},
                        {"Name": "TransactionDate", "Value": 20261102111313},
                    ]
                },
            }
        }
    }
    path = "/api/integrations/mpesa/stk/callback?token=" + "a" * 40
    assert client.post(path, json=callback).json()["ResultCode"] == 0
    assert client.post(path, json=callback).json()["ResultCode"] == 0
    transactions = client.get("/api/finance/transactions", headers=auth).json()
    assert len(transactions) == 1
    assert transactions[0]["amount"] == "10.00000000"
    assert client.get(f"/api/integrations/mpesa/stk-push/{first.json()['id']}", headers=auth).json()["status"] == "SUCCEEDED"


def test_mpesa_stk_is_disabled_without_owner_configuration(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.mpesa.settings.mpesa_enabled", False)
    token = create_user(client, "mpesa.disabled@example.com")
    account_id, _, expense_id = create_ledger_refs(client, token)
    response = client.post(
        "/api/integrations/mpesa/stk-push",
        headers=headers(token),
        json={
            "idempotency_key": "disabled-order",
            "account_id": account_id,
            "category_id": expense_id,
            "amount": "10",
            "phone_number": "254712345678",
            "description": "Test purchase",
        },
    )
    assert response.status_code == 503
