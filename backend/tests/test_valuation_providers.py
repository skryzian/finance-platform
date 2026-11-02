from datetime import date, datetime, timezone
from decimal import Decimal

import httpx
import pytest

from app.providers.alpha_vantage import AlphaVantageDailyProvider
from app.providers.contracts import MarketQuote, ProviderMetadata, ProviderUnavailable
from app.providers.frankfurter_ecb import ExchangeRateQuote, FrankfurterECBProvider


@pytest.mark.asyncio
async def test_alpha_vantage_parses_dated_equity_and_crypto_prices():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["function"] == "DIGITAL_CURRENCY_DAILY":
            return httpx.Response(200, json={
                "Meta Data": {
                    "2. Digital Currency Code": "BTC",
                    "4. Market Code": "USD",
                },
                "Time Series (Digital Currency Daily)": {
                    "2026-11-01": {"4a. close (USD)": "60000.25"},
                    "2026-11-02": {"4a. close (USD)": "61000.50"},
                },
            })
        return httpx.Response(200, json={
            "Meta Data": {"2. Symbol": "IBM"},
            "Time Series (Daily)": {
                "2026-11-01": {"4. close": "250.10"},
                "2026-11-02": {"4. close": "251.20"},
            },
        })

    provider = AlphaVantageDailyProvider("server-only-test-key", transport=httpx.MockTransport(handler))
    equity = await provider.get_quote("ibm", asset_type="EQUITY", currency_code="USD")
    crypto = await provider.get_quote("btc", asset_type="CRYPTO", currency_code="USD")
    assert equity.symbol == "IBM"
    assert equity.price == Decimal("251.20")
    assert equity.metadata.data_timestamp == datetime(2026, 11, 2, tzinfo=timezone.utc)
    assert equity.metadata.data_state == "HISTORICAL"
    assert crypto.symbol == "BTC"
    assert crypto.price == Decimal("61000.50")


@pytest.mark.asyncio
async def test_alpha_vantage_fails_explicitly_when_unconfigured_or_rate_limited():
    with pytest.raises(ProviderUnavailable, match="ALPHA_VANTAGE_API_KEY"):
        await AlphaVantageDailyProvider("").get_quote("IBM")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Note": "provider quota message"})

    provider = AlphaVantageDailyProvider("test-key", transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderUnavailable, match="rate limit"):
        await provider.get_quote("IBM")


@pytest.mark.asyncio
async def test_frankfurter_ecb_parses_and_sorts_daily_observations():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["providers"] == "ecb"
        return httpx.Response(200, json=[
            {"date": "2026-11-02", "base": "EUR", "quote": "USD", "rate": 1.15},
            {"date": "2026-10-30", "base": "EUR", "quote": "USD", "rate": 1.14},
            {"date": "2026-11-01", "base": "EUR", "quote": "USD", "rate": -1},
        ])

    provider = FrankfurterECBProvider(transport=httpx.MockTransport(handler))
    observations = await provider.get_rates(
        "EUR",
        "USD",
        date(2026, 10, 30),
        date(2026, 11, 2),
    )
    assert [item.effective_date for item in observations] == [date(2026, 10, 30), date(2026, 11, 2)]
    assert [item.rate for item in observations] == [Decimal("1.14"), Decimal("1.15")]
    assert all(item.metadata.data_state == "HISTORICAL" for item in observations)


def register_and_login(client, email: str) -> dict[str, str]:
    user = {
        "first_name": "Valuation",
        "last_name": "Tester",
        "email": email,
        "password": "StrongPassword123!",
        "country": "KE",
    }
    assert client.post("/auth/register", json=user).status_code == 201
    tokens = client.post(
        "/auth/login",
        json={"email": email, "password": user["password"]},
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_valuation_endpoints_store_idempotent_source_records(client, monkeypatch):
    headers = register_and_login(client, "valuation.api@example.com")
    from app.core.config import settings

    monkeypatch.setattr(settings, "market_data_provider", "alpha_vantage")
    monkeypatch.setattr(settings, "exchange_rate_provider", "frankfurter_ecb")

    class FakeMarketProvider:
        def __init__(self, _api_key: str):
            pass

        async def get_quote(self, symbol, exchange=None, asset_type="EQUITY", currency_code="USD"):
            return MarketQuote(
                symbol=symbol,
                price=Decimal("251.20"),
                currency_code=currency_code,
                metadata=ProviderMetadata(
                    provider_key="alpha_vantage",
                    retrieved_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
                    data_timestamp=datetime(2026, 11, 2, tzinfo=timezone.utc),
                    data_state="HISTORICAL",
                ),
            )

    class FakeFxProvider:
        def __init__(self):
            pass

        async def get_rates(self, base_currency, quote_currency, start_date, end_date):
            return [
                ExchangeRateQuote(
                    base_currency=base_currency,
                    quote_currency=quote_currency,
                    rate=Decimal("1.15000000"),
                    effective_date=date(2026, 11, 2),
                    metadata=ProviderMetadata(
                        provider_key="frankfurter_ecb",
                        retrieved_at=datetime(2026, 11, 3, tzinfo=timezone.utc),
                        data_state="HISTORICAL",
                    ),
                ),
            ]

    monkeypatch.setattr("app.api.routes.markets.AlphaVantageDailyProvider", FakeMarketProvider)
    monkeypatch.setattr("app.api.routes.markets.FrankfurterECBProvider", FakeFxProvider)
    quote_request = {
        "symbol": "IBM",
        "asset_type": "EQUITY",
        "currency_code": "USD",
    }
    first = client.post("/api/markets/prices/refresh", headers=headers, json=quote_request)
    second = client.post("/api/markets/prices/refresh", headers=headers, json=quote_request)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    history = client.get("/api/markets/prices", headers=headers, params={"symbol": "IBM"})
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["data_state"] == "HISTORICAL"
    assert history.json()[0]["currency_source"] == "USER_ENTERED"

    fx_request = {
        "base_currency": "EUR",
        "quote_currency": "USD",
        "start_date": "2026-11-01",
        "end_date": "2026-11-03",
    }
    first_rates = client.post("/api/markets/exchange-rates/refresh", headers=headers, json=fx_request)
    second_rates = client.post("/api/markets/exchange-rates/refresh", headers=headers, json=fx_request)
    assert first_rates.status_code == second_rates.status_code == 200
    assert first_rates.json()[0]["id"] == second_rates.json()[0]["id"]
    rate_history = client.get(
        "/api/markets/exchange-rates",
        headers=headers,
        params={"base_currency": "EUR", "quote_currency": "USD"},
    )
    assert len(rate_history.json()) == 1
    assert rate_history.json()[0]["provider_key"] == "frankfurter_ecb"
