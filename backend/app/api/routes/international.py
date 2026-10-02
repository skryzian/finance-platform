from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.country import Country
from app.models.currency import Currency
from app.models.user import User
from app.schemas.international import CountryOut, CurrencyOut, UserInternationalSettings, UserInternationalSettingsOut

router = APIRouter(tags=["international"])


@router.get("/countries", response_model=list[CountryOut])
def list_countries(db: Session = Depends(get_db)):
    return db.query(Country).filter(Country.active.is_(True)).all()


@router.get("/currencies", response_model=list[CurrencyOut])
def list_currencies(db: Session = Depends(get_db)):
    return db.query(Currency).filter(Currency.active.is_(True)).all()


@router.get("/settings/international", response_model=UserInternationalSettingsOut)
def get_international_settings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    country = db.query(Country).filter(Country.country_code == (current_user.country or "KE")).first()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")

    return UserInternationalSettingsOut(
        id=current_user.id,
        country_code=current_user.country,
        primary_currency=current_user.currency,
        timezone=current_user.timezone,
        language=current_user.language,
        locale=current_user.locale or country.locale,
        date_format=current_user.date_format,
        time_format=current_user.time_format,
        number_format=current_user.number_format,
    )


@router.put("/settings/international", response_model=UserInternationalSettingsOut)
def update_international_settings(
    payload: UserInternationalSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    country = db.query(Country).filter(Country.country_code == payload.country_code.upper()).first()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not supported")

    currency = db.query(Currency).filter(Currency.code == payload.primary_currency.upper()).first()
    if not currency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Currency not supported")

    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Timezone must be a valid IANA timezone") from exc

    current_user.country = country.country_code
    current_user.currency = payload.primary_currency.upper()
    current_user.timezone = payload.timezone
    current_user.language = payload.language
    current_user.locale = payload.locale
    current_user.date_format = payload.date_format
    current_user.time_format = payload.time_format
    current_user.number_format = payload.number_format
    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)

    return UserInternationalSettingsOut(
        id=current_user.id,
        country_code=current_user.country,
        primary_currency=current_user.currency,
        timezone=current_user.timezone,
        language=current_user.language,
        locale=payload.locale,
        date_format=payload.date_format,
        time_format=payload.time_format,
        number_format=payload.number_format,
    )
