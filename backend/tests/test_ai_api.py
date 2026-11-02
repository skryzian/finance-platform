import asyncio
from types import SimpleNamespace

import pytest

from app.ai.service import AIAnswer, AIUnavailable
from app.api.routes.ai import get_ai_rate_limiter, get_ai_service_dependency
from app.db.database import SessionLocal
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.ai_usage import AIUsage


class FakeAIService:
    def __init__(self, should_fail: bool = False):
        self.provider = SimpleNamespace(model_name="test-model")
        self.should_fail = should_fail
        self.closed = False
        self.should_timeout = False
        self.context = None

    async def answer(self, prompt, context, max_output_tokens):
        self.context = context
        if self.should_timeout:
            raise asyncio.TimeoutError()
        if self.should_fail:
            raise AIUnavailable("private provider error")
        assert "accounts" in context["verified_context"]
        assert context["source_references"]
        return AIAnswer(
            text="The connected application has no verified transaction data for this question.",
            provider_key="test-provider",
            model_name="test-model",
            source_references=context.get("source_references", []),
            input_tokens=12,
            output_tokens=14,
        )

    async def aclose(self):
        self.closed = True


class FakeRateLimiter:
    def __init__(self, permitted=True):
        self.permitted = permitted

    async def acquire(self, user_id, now):
        return self.permitted


def create_user(client, email):
    response = client.post(
        "/auth/register",
        json={
            "first_name": "Copilot",
            "last_name": "Tester",
            "email": email,
            "password": "StrongPassword123!",
            "country": "KE",
        },
    )
    assert response.status_code == 201, response.text
    response = client.post("/auth/login", json={"email": email, "password": "StrongPassword123!"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def install_overrides(client, service=None, limiter=None):
    client.app.dependency_overrides[get_ai_service_dependency] = lambda: service or FakeAIService()
    client.app.dependency_overrides[get_ai_rate_limiter] = lambda: limiter or FakeRateLimiter()


def enable_ai_data_access(client, token):
    response = client.put(
        "/api/ai/data-access",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": True},
    )
    assert response.status_code == 200


def test_chat_requires_authentication(client):
    install_overrides(client)
    response = client.post("/api/ai/chat", json={"question": "What is my net worth?"})
    assert response.status_code == 401


def test_chat_returns_usage_without_saving_prompt_by_default(client):
    token = create_user(client, "copilot.private@example.com")
    enable_ai_data_access(client, token)
    install_overrides(client)

    response = client.post(
        "/api/ai/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What is my current net worth?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "no verified transaction data" in body["answer"]
    assert body["conversation_id"] is None
    assert body["input_tokens"] == 12

    with SessionLocal() as db:
        usage = db.query(AIUsage).one()
        assert usage.status == "SUCCEEDED"
        assert usage.input_tokens == 12
        assert db.query(AIConversation).count() == 0
        assert db.query(AIMessage).count() == 0


def test_rate_limited_request_is_not_sent_to_provider(client):
    token = create_user(client, "copilot.limited@example.com")
    enable_ai_data_access(client, token)
    service = FakeAIService()
    install_overrides(client, service=service, limiter=FakeRateLimiter(permitted=False))

    response = client.post(
        "/api/ai/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Explain this month's expenses."},
    )
    assert response.status_code == 429
    assert service.closed is True


def test_provider_failure_returns_sanitized_response_and_is_audited(client):
    token = create_user(client, "copilot.failure@example.com")
    enable_ai_data_access(client, token)
    service = FakeAIService(should_fail=True)
    install_overrides(client, service=service)

    response = client.post(
        "/api/ai/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What changed?"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Financial Copilot is temporarily unavailable"
    assert "private provider error" not in response.text

    with SessionLocal() as db:
        usage = db.query(AIUsage).one()
        assert usage.status == "FAILED"
        assert usage.error_code == "PROVIDER_UNAVAILABLE"


def test_timeout_returns_sanitized_response_and_is_audited(client):
    token = create_user(client, "copilot.timeout@example.com")
    enable_ai_data_access(client, token)
    service = FakeAIService()
    service.should_timeout = True
    install_overrides(client, service=service)

    response = client.post(
        "/api/ai/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "What changed?"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Financial Copilot is temporarily unavailable"

    with SessionLocal() as db:
        usage = db.query(AIUsage).one()
        assert usage.status == "FAILED"
        assert usage.error_code == "TIMEOUT"


def test_chat_history_is_opt_in_and_user_scoped(client):
    first_token = create_user(client, "copilot.history.one@example.com")
    second_token = create_user(client, "copilot.history.two@example.com")
    enable_ai_data_access(client, first_token)
    install_overrides(client)
    first_headers = {"Authorization": f"Bearer {first_token}"}
    second_headers = {"Authorization": f"Bearer {second_token}"}

    response = client.put("/api/ai/history", headers=first_headers, json={"enabled": True})
    assert response.status_code == 200
    response = client.post("/api/ai/chat", headers=first_headers, json={"question": "How can I review my spending?"})
    assert response.status_code == 200, response.text
    conversation_id = response.json()["conversation_id"]
    assert conversation_id is not None

    response = client.get(f"/api/ai/conversations/{conversation_id}", headers=second_headers)
    assert response.status_code == 404

    response = client.get(f"/api/ai/conversations/{conversation_id}", headers=first_headers)
    assert response.status_code == 200
    assert len(response.json()["messages"]) == 2

    response = client.delete(f"/api/ai/conversations/{conversation_id}", headers=first_headers)
    assert response.status_code == 204
    response = client.get(f"/api/ai/conversations/{conversation_id}", headers=first_headers)
    assert response.status_code == 404


def test_blank_and_oversized_questions_are_rejected(client, monkeypatch):
    token = create_user(client, "copilot.validation@example.com")
    monkeypatch.setattr("app.api.routes.ai.settings.ai_max_prompt_characters", 20)
    install_overrides(client)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post("/api/ai/chat", headers=headers, json={"question": "  "}).status_code == 422
    assert client.post("/api/ai/chat", headers=headers, json={"question": "a" * 21}).status_code == 413


def test_ai_data_access_is_opt_in_and_revocable(client):
    token = create_user(client, "copilot.consent@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    install_overrides(client)

    assert client.get("/api/ai/data-access", headers=headers).json() == {"enabled": False}
    response = client.post("/api/ai/chat", headers=headers, json={"question": "What is my balance?"})
    assert response.status_code == 403
    enable_ai_data_access(client, token)
    assert client.put("/api/ai/data-access", headers=headers, json={"enabled": False}).json() == {"enabled": False}
    response = client.post("/api/ai/chat", headers=headers, json={"question": "What is my balance?"})
    assert response.status_code == 403


def test_ai_retrieval_uses_only_the_opted_in_users_ledger(client):
    first_token = create_user(client, "copilot.data.first@example.com")
    second_token = create_user(client, "copilot.data.second@example.com")
    first_headers = {"Authorization": f"Bearer {first_token}"}
    for token, name, balance in (
        (first_token, "Private first account", "150"),
        (second_token, "Private second account", "9000"),
    ):
        response = client.post(
            "/api/finance/accounts",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": name,
                "account_type": "CASH",
                "currency_code": "KES",
                "opening_balance": balance,
            },
        )
        assert response.status_code == 201
    enable_ai_data_access(client, first_token)
    service = FakeAIService()
    install_overrides(client, service=service)

    response = client.post(
        "/api/ai/chat",
        headers=first_headers,
        json={"question": "Summarize my accounts."},
    )
    assert response.status_code == 200
    context = service.context["verified_context"]
    assert context["accounts"] == [{
        "name": "Private first account",
        "type": "CASH",
        "currency": "KES",
        "balance": "150.00000000",
    }]
    assert "Private second account" not in str(context)
    assert response.json()["sources"]
