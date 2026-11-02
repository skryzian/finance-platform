from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.currency import Currency
from app.models.market_asset import MarketAsset
from app.models.valuation import ExchangeRateObservation, MarketPriceHistory
from app.models.user import User
from app.providers.alpha_vantage import AlphaVantageDailyProvider
from app.providers.contracts import ProviderUnavailable
from app.providers.frankfurter_ecb import FrankfurterECBProvider
from app.schemas.intelligence import MarketAssetOut
from app.schemas.valuation import (
    ExchangeRateOut,
    ExchangeRateRefreshIn,
    MarketPriceOut,
    MarketPriceRefreshIn,
)

router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/assets", response_model=list[MarketAssetOut])
def list_market_assets(
    search: str | None = Query(default=None, max_length=80),
    asset_type: str | None = Query(default=None, max_length=50),
    exchange: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    query = db.query(MarketAsset).filter(MarketAsset.is_active.is_(True))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter((MarketAsset.symbol.ilike(pattern)) | (MarketAsset.name.ilike(pattern)))
    if asset_type:
        query = query.filter(MarketAsset.asset_type == asset_type)
    if exchange:
        query = query.filter(MarketAsset.exchange == exchange)
    return query.order_by(MarketAsset.symbol).limit(limit).all()


@router.get("/prices", response_model=list[MarketPriceOut])
def list_market_prices(
    symbol: str = Query(..., min_length=1, max_length=32),
    asset_type: str | None = Query(default=None, max_length=16),
    exchange: str | None = Query(default=None, max_length=50),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End date must be on or after start date")
    query = db.query(MarketPriceHistory).filter(
        MarketPriceHistory.symbol == symbol.strip().upper(),
    )
    if asset_type:
        query = query.filter(MarketPriceHistory.asset_type == asset_type.upper())
    if exchange is not None:
        query = query.filter(MarketPriceHistory.exchange == exchange.strip().upper())
    if start_date:
        query = query.filter(MarketPriceHistory.effective_date >= start_date)
    if end_date:
        query = query.filter(MarketPriceHistory.effective_date <= end_date)
    return query.order_by(
        MarketPriceHistory.effective_date.desc(),
        MarketPriceHistory.id.desc(),
    ).limit(limit).all()


@router.post("/prices/refresh", response_model=MarketPriceOut)
async def refresh_market_price(
    payload: MarketPriceRefreshIn,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    if settings.market_data_provider != "alpha_vantage":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Alpha Vantage is not the configured market data provider")
    currency = db.query(Currency).filter(
        Currency.code == payload.currency_code,
        Currency.active.is_(True),
    ).first()
    if currency is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Currency is not supported")
    provider = AlphaVantageDailyProvider(settings.alpha_vantage_api_key)
    try:
        quote = await provider.get_quote(
            payload.symbol,
            exchange=payload.exchange,
            asset_type=payload.asset_type,
            currency_code=payload.currency_code,
        )
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if quote.currency_code != payload.currency_code:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Provider currency did not match the requested currency")
    if quote.metadata.data_timestamp is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Provider response did not include an observation date")
    effective_date = quote.metadata.data_timestamp.date()
    exchange = payload.exchange or ""
    record = db.query(MarketPriceHistory).filter(
        MarketPriceHistory.symbol == quote.symbol,
        MarketPriceHistory.asset_type == payload.asset_type,
        MarketPriceHistory.exchange == exchange,
        MarketPriceHistory.effective_date == effective_date,
        MarketPriceHistory.provider_key == quote.metadata.provider_key,
    ).first()
    if record is None:
        record = MarketPriceHistory(
            symbol=quote.symbol,
            asset_type=payload.asset_type,
            exchange=exchange,
            currency_code=quote.currency_code,
            currency_source="PROVIDER" if payload.asset_type == "CRYPTO" else "USER_ENTERED",
            price=quote.price,
            effective_date=effective_date,
            provider_key=quote.metadata.provider_key,
            data_state=quote.metadata.data_state,
            retrieved_at=quote.metadata.retrieved_at,
        )
        db.add(record)
    else:
        record.currency_code = quote.currency_code
        record.currency_source = "PROVIDER" if payload.asset_type == "CRYPTO" else "USER_ENTERED"
        record.price = quote.price
        record.data_state = quote.metadata.data_state
        record.retrieved_at = quote.metadata.retrieved_at
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Price observation was concurrently stored; retry the request") from exc
    db.refresh(record)
    return record


@router.get("/exchange-rates", response_model=list[ExchangeRateOut])
def list_exchange_rate_history(
    base_currency: str = Query(..., min_length=3, max_length=3),
    quote_currency: str = Query(..., min_length=3, max_length=3),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    base = base_currency.upper()
    quote = quote_currency.upper()
    if base == quote:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Base and quote currencies must differ")
    if start_date and end_date and end_date < start_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="End date must be on or after start date")
    query = db.query(ExchangeRateObservation).filter(
        ExchangeRateObservation.base_currency == base,
        ExchangeRateObservation.quote_currency == quote,
    )
    if start_date:
        query = query.filter(ExchangeRateObservation.effective_date >= start_date)
    if end_date:
        query = query.filter(ExchangeRateObservation.effective_date <= end_date)
    return query.order_by(
        ExchangeRateObservation.effective_date.desc(),
        ExchangeRateObservation.id.desc(),
    ).limit(limit).all()


@router.post("/exchange-rates/refresh", response_model=list[ExchangeRateOut])
async def refresh_exchange_rate_history(
    payload: ExchangeRateRefreshIn,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    if settings.exchange_rate_provider != "frankfurter_ecb":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Frankfurter/ECB is not the configured exchange-rate provider")
    currencies = {
        row.code for row in db.query(Currency.code).filter(
            Currency.code.in_((payload.base_currency, payload.quote_currency)),
            Currency.active.is_(True),
        ).all()
    }
    if currencies != {payload.base_currency, payload.quote_currency}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Base and quote currencies must be supported")
    provider = FrankfurterECBProvider()
    try:
        quotes = await provider.get_rates(
            payload.base_currency,
            payload.quote_currency,
            payload.start_date,
            payload.end_date,
        )
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if not quotes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frankfurter/ECB returned no observations for this date range")

    retrieved_at = datetime.now(timezone.utc)
    records: list[ExchangeRateObservation] = []
    for quote in quotes:
        record = db.query(ExchangeRateObservation).filter(
            ExchangeRateObservation.base_currency == quote.base_currency,
            ExchangeRateObservation.quote_currency == quote.quote_currency,
            ExchangeRateObservation.effective_date == quote.effective_date,
            ExchangeRateObservation.provider_key == quote.metadata.provider_key,
        ).first()
        if record is None:
            record = ExchangeRateObservation(
                base_currency=quote.base_currency,
                quote_currency=quote.quote_currency,
                rate=quote.rate,
                effective_date=quote.effective_date,
                provider_key=quote.metadata.provider_key,
                data_state=quote.metadata.data_state,
                retrieved_at=retrieved_at,
            )
            db.add(record)
        else:
            record.rate = quote.rate
            record.data_state = quote.metadata.data_state
            record.retrieved_at = retrieved_at
        records.append(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Exchange-rate observations were concurrently stored; retry the request") from exc
    for record in records:
        db.refresh(record)
    return records
