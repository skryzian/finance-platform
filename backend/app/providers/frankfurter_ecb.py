from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.providers.contracts import ProviderMetadata, ProviderUnavailable


@dataclass(frozen=True)
class ExchangeRateQuote:
    base_currency: str
    quote_currency: str
    rate: Decimal
    effective_date: date
    metadata: ProviderMetadata


class FrankfurterECBProvider:
    provider_key = "frankfurter_ecb"
    base_url = "https://api.frankfurter.dev/v2/rates"

    def __init__(
        self,
        timeout_seconds: float = 15,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def get_rates(
        self,
        base_currency: str,
        quote_currency: str,
        start_date: date,
        end_date: date,
    ) -> list[ExchangeRateQuote]:
        params = {
            "base": base_currency.upper(),
            "quotes": quote_currency.upper(),
            "providers": "ecb",
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
        }
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            try:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderUnavailable("Frankfurter/ECB request failed; retry later.") from exc
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise ProviderUnavailable("Frankfurter/ECB returned an invalid response.") from exc
        if not isinstance(payload, list):
            raise ProviderUnavailable("Frankfurter/ECB returned an invalid response.")

        retrieved_at = datetime.now(timezone.utc)
        quotes: list[ExchangeRateQuote] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                observed_date = date.fromisoformat(str(item["date"]))
                base = str(item["base"]).upper()
                quote = str(item["quote"]).upper()
                rate = Decimal(str(item["rate"]))
            except (KeyError, ValueError, InvalidOperation):
                continue
            if (
                base != base_currency.upper()
                or quote != quote_currency.upper()
                or observed_date < start_date
                or observed_date > end_date
                or not rate.is_finite()
                or rate <= 0
            ):
                continue
            quotes.append(ExchangeRateQuote(
                base_currency=base,
                quote_currency=quote,
                rate=rate,
                effective_date=observed_date,
                metadata=ProviderMetadata(
                    provider_key=self.provider_key,
                    retrieved_at=retrieved_at,
                    data_timestamp=datetime.combine(
                        observed_date,
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    verification_status="PROVIDER_RESPONSE",
                    data_state="HISTORICAL",
                    source_url=self.base_url,
                ),
            ))
        return sorted(quotes, key=lambda quote: quote.effective_date)
