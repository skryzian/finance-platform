from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.providers.contracts import MarketQuote, ProviderMetadata, ProviderUnavailable


class AlphaVantageDailyProvider:
    provider_key = "alpha_vantage"
    base_url = "https://www.alphavantage.co/query"

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 15,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def get_quote(
        self,
        symbol: str,
        exchange: str | None = None,
        asset_type: str = "EQUITY",
        currency_code: str = "USD",
    ) -> MarketQuote:
        if not self.api_key:
            raise ProviderUnavailable("Alpha Vantage is not configured. Set ALPHA_VANTAGE_API_KEY on the server.")
        is_crypto = asset_type.upper() == "CRYPTO"
        function = "DIGITAL_CURRENCY_DAILY" if is_crypto else "TIME_SERIES_DAILY"
        params: dict[str, str] = {
            "function": function,
            "symbol": symbol.strip().upper(),
            "apikey": self.api_key,
        }
        if is_crypto:
            params["market"] = currency_code.upper()
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            try:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderUnavailable("Alpha Vantage request failed; retry later.") from exc
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise ProviderUnavailable("Alpha Vantage returned an invalid response.") from exc
        if not isinstance(payload, dict):
            raise ProviderUnavailable("Alpha Vantage returned an invalid response.")
        if any(key in payload for key in ("Error Message", "Note", "Information")):
            raise ProviderUnavailable("Alpha Vantage rejected the request or rate limit was reached.")

        metadata_key = "Meta Data"
        metadata = payload.get(metadata_key)
        expected_symbol_key = "2. Digital Currency Code" if is_crypto else "2. Symbol"
        if isinstance(metadata, dict) and metadata.get(expected_symbol_key):
            provider_symbol = str(metadata[expected_symbol_key]).upper()
            if provider_symbol != symbol.strip().upper():
                raise ProviderUnavailable("Alpha Vantage returned a different symbol than requested.")
        if is_crypto and isinstance(metadata, dict) and metadata.get("4. Market Code"):
            if str(metadata["4. Market Code"]).upper() != currency_code.upper():
                raise ProviderUnavailable("Alpha Vantage returned a different crypto quote currency.")

        series_key = "Time Series (Digital Currency Daily)" if is_crypto else "Time Series (Daily)"
        series = payload.get(series_key)
        if not isinstance(series, dict) or not series:
            raise ProviderUnavailable("Alpha Vantage returned no daily observations for this symbol.")
        dated_values: list[tuple[date, Decimal]] = []
        for date_text, values in series.items():
            if not isinstance(values, dict):
                continue
            price_key = next(
                (key for key in values if key.startswith("4a. close (")),
                None,
            ) if is_crypto else "4. close"
            if price_key is None:
                continue
            if is_crypto:
                returned_currency = price_key.rsplit("(", 1)[-1].rstrip(")").upper()
                if returned_currency != currency_code.upper():
                    raise ProviderUnavailable("Alpha Vantage returned a different crypto quote currency.")
            try:
                observed_date = date.fromisoformat(date_text)
                price = Decimal(str(values[price_key]))
            except (ValueError, InvalidOperation):
                continue
            if price.is_finite() and price > 0:
                dated_values.append((observed_date, price))
        if not dated_values:
            raise ProviderUnavailable("Alpha Vantage returned no valid daily closing prices.")

        effective_date, price = max(dated_values, key=lambda item: item[0])
        timestamp = datetime.combine(effective_date, time.min, tzinfo=timezone.utc)
        return MarketQuote(
            symbol=symbol.strip().upper(),
            price=price,
            currency_code=currency_code.upper(),
            metadata=ProviderMetadata(
                provider_key=self.provider_key,
                retrieved_at=datetime.now(timezone.utc),
                data_timestamp=timestamp,
                verification_status="PROVIDER_RESPONSE",
                data_state="HISTORICAL",
                source_url=self.base_url,
            ),
        )
