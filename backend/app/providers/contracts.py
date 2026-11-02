from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderMetadata:
    provider_key: str
    retrieved_at: datetime
    published_at: datetime | None = None
    data_timestamp: datetime | None = None
    verification_status: str = "UNVERIFIED"
    data_state: str = "HISTORICAL"
    source_url: str | None = None


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price: Decimal
    currency_code: str
    metadata: ProviderMetadata


@dataclass(frozen=True)
class NewsItem:
    headline: str
    url: str
    published_at: datetime | None
    metadata: ProviderMetadata


class MarketDataProvider(Protocol):
    provider_key: str

    async def get_quote(
        self,
        symbol: str,
        exchange: str | None = None,
        asset_type: str = "EQUITY",
        currency_code: str = "USD",
    ) -> MarketQuote:
        """Return a sourced quote or raise ProviderUnavailable."""
        ...


class ExchangeRateProvider(Protocol):
    provider_key: str

    async def get_rate(self, base_currency: str, quote_currency: str, at: datetime | None = None) -> tuple[Decimal, ProviderMetadata]:
        ...


class NewsProvider(Protocol):
    provider_key: str

    async def search(self, query: str, country_code: str | None = None) -> list[NewsItem]:
        ...


class CompanyDataProvider(Protocol):
    provider_key: str

    async def get_company_facts(self, symbol: str, exchange: str | None = None) -> dict[str, Any]:
        ...


class CryptoDataProvider(Protocol):
    provider_key: str

    async def get_asset_data(self, asset_id: str) -> dict[str, Any]:
        ...


class LoanDataProvider(Protocol):
    provider_key: str

    async def search_products(self, country_code: str, currency_code: str) -> list[dict[str, Any]]:
        ...


class PromotionProvider(Protocol):
    provider_key: str

    async def search_promotions(self, country_code: str) -> list[dict[str, Any]]:
        ...


class ProviderUnavailable(RuntimeError):
    pass


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[tuple[str, str], object] = {}

    def register(self, capability: str, provider: object, provider_key: str) -> None:
        self._providers[(capability, provider_key)] = provider

    def get(self, capability: str, provider_key: str) -> object:
        provider = self._providers.get((capability, provider_key))
        if provider is None:
            raise ProviderUnavailable(f"No configured {capability} provider: {provider_key}")
        return provider
