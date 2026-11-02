from decimal import Decimal
from uuid import uuid4


def register_and_login(client, email):
    payload = {
        "first_name": "Ledger",
        "last_name": "Tester",
        "email": email,
        "password": "StrongPassword123!",
        "country": "KE",
    }
    assert client.post("/auth/register", json=payload).status_code == 201
    response = client.post(
        "/auth/login",
        json={"email": email, "password": payload["password"]},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_ledger_transfers_are_net_zero_and_retries_are_idempotent(client):
    headers = register_and_login(client, "ledger.one@example.com")
    first = client.post(
        "/api/finance/accounts",
        headers=headers,
        json={
            "name": "Main account",
            "account_type": "BANK",
            "currency_code": "KES",
            "opening_balance": "1000.00",
        },
    )
    second = client.post(
        "/api/finance/accounts",
        headers=headers,
        json={
            "name": "Wallet",
            "account_type": "MOBILE_MONEY",
            "currency_code": "KES",
        },
    )
    assert first.status_code == second.status_code == 201
    first_id, second_id = first.json()["id"], second.json()["id"]

    income_category = client.post(
        "/api/finance/categories",
        headers=headers,
        json={"name": "Salary", "category_type": "INCOME"},
    ).json()
    expense_category = client.post(
        "/api/finance/categories",
        headers=headers,
        json={"name": "Food", "category_type": "EXPENSE"},
    ).json()

    common = {
        "account_id": first_id,
        "currency_code": "KES",
        "description": "Ledger entry",
        "transaction_date": "2026-10-15T12:00:00+03:00",
    }
    income = {
        **common,
        "idempotency_key": "income-operation-1",
        "transaction_type": "INCOME",
        "category_id": income_category["id"],
        "amount": "300.00",
    }
    response = client.post("/api/finance/transactions", headers=headers, json=income)
    assert response.status_code == 201, response.text
    assert client.post("/api/finance/transactions", headers=headers, json=income).status_code == 200

    expense = {
        **common,
        "idempotency_key": "expense-operation-1",
        "transaction_type": "EXPENSE",
        "category_id": expense_category["id"],
        "amount": "100.00",
    }
    assert client.post("/api/finance/transactions", headers=headers, json=expense).status_code == 201

    transfer = {
        **common,
        "idempotency_key": "transfer-operation-1",
        "transaction_type": "TRANSFER",
        "transfer_account_id": second_id,
        "amount": "200.00",
    }
    assert client.post("/api/finance/transactions", headers=headers, json=transfer).status_code == 201
    changed_replay = {**income, "amount": "301.00"}
    assert client.post(
        "/api/finance/transactions",
        headers=headers,
        json=changed_replay,
    ).status_code == 409

    accounts = client.get("/api/finance/accounts", headers=headers)
    assert accounts.status_code == 200
    balances = {account["id"]: Decimal(str(account["current_balance"])) for account in accounts.json()}
    assert balances == {first_id: Decimal("1000.00"), second_id: Decimal("200.00")}

    summary = client.get(
        "/api/finance/reports/summary",
        headers=headers,
        params={"start_date": "2026-10-01", "end_date": "2026-10-31"},
    )
    assert summary.status_code == 200
    kes = next(item for item in summary.json()["by_currency"] if item["currency_code"] == "KES")
    assert Decimal(str(kes["total_income"])) == Decimal("300.00")
    assert Decimal(str(kes["total_expenses"])) == Decimal("100.00")
    assert Decimal(str(kes["net_cash_flow"])) == Decimal("200.00")
    assert Decimal(str(kes["net_worth"])) == Decimal("1200.00")


def test_ledger_enforces_ownership_currency_precision_and_reversals(client):
    owner_headers = register_and_login(client, "ledger.owner@example.com")
    other_headers = register_and_login(client, "ledger.other@example.com")
    account = client.post(
        "/api/finance/accounts",
        headers=owner_headers,
        json={"name": "Cash", "account_type": "CASH", "currency_code": "KES"},
    ).json()
    other_account = client.post(
        "/api/finance/accounts",
        headers=other_headers,
        json={"name": "Private", "account_type": "CASH", "currency_code": "KES"},
    ).json()
    income_category = client.post(
        "/api/finance/categories",
        headers=owner_headers,
        json={"name": "Gift", "category_type": "INCOME"},
    ).json()

    base = {
        "account_id": account["id"],
        "category_id": income_category["id"],
        "transaction_type": "INCOME",
        "amount": "100.00",
        "currency_code": "KES",
        "description": "Gift",
        "transaction_date": "2026-10-15T12:00:00Z",
    }
    cross_user = client.post(
        "/api/finance/transactions",
        headers=owner_headers,
        json={
            **base,
            "idempotency_key": "cross-user",
            "category_id": None,
            "transaction_type": "TRANSFER",
            "transfer_account_id": other_account["id"],
        },
    )
    assert cross_user.status_code == 404

    jpy_account = client.post(
        "/api/finance/accounts",
        headers=owner_headers,
        json={"name": "Yen cash", "account_type": "CASH", "currency_code": "JPY"},
    ).json()
    jpy_category = client.post(
        "/api/finance/categories",
        headers=owner_headers,
        json={"name": "Yen income", "category_type": "INCOME"},
    ).json()
    precision_failure = client.post(
        "/api/finance/transactions",
        headers=owner_headers,
        json={
            **base,
            "idempotency_key": "jpy-precision",
            "account_id": jpy_account["id"],
            "category_id": jpy_category["id"],
            "currency_code": "JPY",
            "amount": "100.25",
        },
    )
    assert precision_failure.status_code == 422

    created = client.post(
        "/api/finance/transactions",
        headers=owner_headers,
        json={**base, "idempotency_key": "gift-original"},
    )
    assert created.status_code == 201
    reversed_transaction = client.post(
        f"/api/finance/transactions/{created.json()['id']}/reverse",
        headers=owner_headers,
        params={"idempotency_key": "gift-reversal"},
        json=None,
    )
    assert reversed_transaction.status_code == 422

    expense_category = client.post(
        "/api/finance/categories",
        headers=owner_headers,
        json={"name": "Reversal", "category_type": "EXPENSE"},
    ).json()
    reversed_transaction = client.post(
        f"/api/finance/transactions/{created.json()['id']}/reverse",
        headers=owner_headers,
        params={"idempotency_key": "gift-reversal", "category_id": expense_category["id"]},
    )
    assert reversed_transaction.status_code == 201, reversed_transaction.text
    assert reversed_transaction.json()["reversal_of_id"] == created.json()["id"]
    assert client.post(
        f"/api/finance/transactions/{created.json()['id']}/reverse",
        headers=owner_headers,
        params={"idempotency_key": "gift-reversal-duplicate", "category_id": expense_category["id"]},
    ).status_code == 409


def test_budgets_and_balance_sheet_are_currency_scoped(client):
    headers = register_and_login(client, "ledger.budget@example.com")
    account = client.post(
        "/api/finance/accounts",
        headers=headers,
        json={
            "name": "Checking",
            "account_type": "BANK",
            "currency_code": "KES",
            "opening_balance": "1000.00",
        },
    ).json()
    category = client.post(
        "/api/finance/categories",
        headers=headers,
        json={"name": "Transport", "category_type": "EXPENSE"},
    ).json()
    transaction = client.post(
        "/api/finance/transactions",
        headers=headers,
        json={
            "idempotency_key": "transport-1",
            "account_id": account["id"],
            "category_id": category["id"],
            "transaction_type": "EXPENSE",
            "amount": "120.00",
            "currency_code": "KES",
            "description": "Bus fare",
            "transaction_date": "2026-10-16T10:00:00Z",
        },
    )
    assert transaction.status_code == 201
    budget = client.post(
        "/api/finance/budgets",
        headers=headers,
        json={
            "name": "October transport",
            "category_id": category["id"],
            "amount": "300.00",
            "currency_code": "KES",
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
        },
    )
    assert budget.status_code == 201, budget.text
    budget_list = client.get("/api/finance/budgets", headers=headers)
    assert Decimal(str(budget_list.json()[0]["spent"])) == Decimal("120.00")

    asset = client.post(
        "/api/finance/assets",
        headers=headers,
        json={
            "name": "Home contents",
            "record_type": "PERSONAL_PROPERTY",
            "currency_code": "KES",
            "amount": "500.00",
            "valued_at": "2026-10-16T00:00:00Z",
        },
    )
    liability = client.post(
        "/api/finance/liabilities",
        headers=headers,
        json={
            "name": "Loan",
            "record_type": "PERSONAL_LOAN",
            "currency_code": "KES",
            "amount": "200.00",
            "valued_at": "2026-10-16T00:00:00Z",
        },
    )
    assert asset.status_code == liability.status_code == 201
    summary = client.get(
        "/api/finance/reports/summary",
        headers=headers,
        params={"start_date": "2026-10-01", "end_date": "2026-10-31"},
    )
    kes = next(item for item in summary.json()["by_currency"] if item["currency_code"] == "KES")
    assert Decimal(str(kes["total_assets"])) == Decimal("1380.00")
    assert Decimal(str(kes["total_liabilities"])) == Decimal("200.00")
    assert Decimal(str(kes["net_worth"])) == Decimal("1180.00")


def test_offline_sync_is_idempotent_and_returns_explicit_conflicts(client):
    headers = register_and_login(client, "ledger.sync@example.com")
    account_client_id = str(uuid4())
    category_client_id = str(uuid4())
    account_input = {
        "client_id": account_client_id,
        "base_version": 0,
        "name": "Offline checking",
        "account_type": "BANK",
        "currency_code": "KES",
        "opening_balance": "1000.00",
    }
    category_input = {
        "client_id": category_client_id,
        "base_version": 0,
        "name": "Offline groceries",
        "category_type": "EXPENSE",
    }

    created = client.post(
        "/api/finance/sync/push",
        headers=headers,
        json={"accounts": [account_input], "categories": [category_input]},
    )
    assert created.status_code == 200, created.text
    results = created.json()["results"]
    assert [item["status"] for item in results] == ["APPLIED", "APPLIED"]
    account_remote_id = results[0]["remote_id"]
    category_remote_id = results[1]["remote_id"]
    assert [item["server_version"] for item in results] == [1, 1]

    replay = client.post(
        "/api/finance/sync/push",
        headers=headers,
        json={"accounts": [account_input], "categories": [category_input]},
    )
    assert [item["status"] for item in replay.json()["results"]] == ["APPLIED", "APPLIED"]
    assert [item["remote_id"] for item in replay.json()["results"]] == [account_remote_id, category_remote_id]

    update = {
        **account_input,
        "base_version": 1,
        "name": "Renamed offline checking",
    }
    updated = client.post(
        "/api/finance/sync/push",
        headers=headers,
        json={"accounts": [update]},
    )
    assert updated.json()["results"][0]["server_version"] == 2
    stale_update = {**account_input, "name": "Stale edit"}
    conflict = client.post(
        "/api/finance/sync/push",
        headers=headers,
        json={"accounts": [stale_update]},
    )
    conflict_result = conflict.json()["results"][0]
    assert conflict_result["status"] == "CONFLICT"
    assert conflict_result["server_version"] == 2
    assert conflict_result["server_data"]["name"] == "Renamed offline checking"

    transaction = {
        "local_id": str(uuid4()),
        "idempotency_key": str(uuid4()),
        "account_client_id": account_client_id,
        "category_client_id": category_client_id,
        "transaction_type": "EXPENSE",
        "amount": "25.50",
        "currency_code": "KES",
        "description": "Offline purchase",
        "transaction_date": "2026-10-18T12:00:00Z",
    }
    pushed = client.post(
        "/api/finance/sync/push",
        headers=headers,
        json={"transactions": [transaction]},
    )
    assert pushed.status_code == 200
    transaction_remote_id = pushed.json()["results"][0]["remote_id"]
    assert pushed.json()["results"][0]["status"] == "APPLIED"
    replayed_transaction = client.post(
        "/api/finance/sync/push",
        headers=headers,
        json={"transactions": [transaction]},
    )
    assert replayed_transaction.json()["results"][0]["remote_id"] == transaction_remote_id
    changed_replay = {**transaction, "amount": "26.00"}
    idempotency_conflict = client.post(
        "/api/finance/sync/push",
        headers=headers,
        json={"transactions": [changed_replay]},
    )
    conflict_result = idempotency_conflict.json()["results"][0]
    assert conflict_result["status"] == "CONFLICT"
    assert conflict_result["remote_id"] == transaction_remote_id
    assert Decimal(conflict_result["server_data"]["amount"]) == Decimal("25.50")

    first_page = client.get("/api/finance/sync/pull", headers=headers, params={"cursor": 0, "limit": 2})
    assert first_page.status_code == 200
    assert [event["version"] for event in first_page.json()["events"]] == [1, 2]
    assert first_page.json()["cursor"] == 2
    second_page = client.get(
        "/api/finance/sync/pull",
        headers=headers,
        params={"cursor": first_page.json()["cursor"], "limit": 2},
    )
    assert [event["version"] for event in second_page.json()["events"]] == [3, 4]
    assert second_page.json()["cursor"] == 4
    transaction_event = second_page.json()["events"][1]
    assert Decimal(transaction_event["payload"]["account_balances"][str(account_remote_id)]) == Decimal("974.50")
    other_headers = register_and_login(client, "ledger.sync.other@example.com")
    assert client.get(
        "/api/finance/sync/pull",
        headers=other_headers,
        params={"cursor": 0},
    ).json()["events"] == []
