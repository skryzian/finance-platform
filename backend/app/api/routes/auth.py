from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.country import Country
from app.models.currency import Currency
from app.models.session import Session as AuthSession
from app.models.user import User
from app.schemas.user import ProfileUpdate, TokenPair, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    country_code = payload.country.upper()
    country = db.query(Country).filter(Country.country_code == country_code, Country.active.is_(True)).first()
    if country is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Country is not supported")
    currency_code = (payload.currency or country.default_currency).upper()
    currency = db.query(Currency).filter(Currency.code == currency_code, Currency.active.is_(True)).first()
    if currency is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency is not supported")
    timezone_name = payload.timezone or country.default_timezone
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Timezone must be a valid IANA timezone") from exc

    user = User(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=payload.email.lower(),
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        country=country_code,
        currency=currency_code,
        timezone=timezone_name,
        language=payload.language or country.locale.split("_")[0],
        locale=payload.locale or country.locale,
        date_format=payload.date_format,
        time_format=payload.time_format,
        number_format=payload.number_format,
        ai_history_enabled=settings.ai_history_enabled_by_default,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    refresh_hash = hash_password(refresh_token)
    db.add(
        AuthSession(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            user_agent="unknown",
            ip_address="unknown",
            expires_at=datetime.now(timezone.utc).replace(microsecond=0),
        )
    )
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPair)
def refresh_token(token: str, db: Session = Depends(get_db)):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Refresh token flow is scaffolded for Phase 1")


@router.post("/logout")
def logout_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(AuthSession).filter(AuthSession.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/profile", response_model=UserOut)
def update_profile(payload: ProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.first_name is not None:
        current_user.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        current_user.last_name = payload.last_name.strip()
    if payload.phone is not None:
        current_user.phone = payload.phone
    if payload.country is not None:
        current_user.country = payload.country.upper()
    if payload.currency is not None:
        current_user.currency = payload.currency.upper()
    if payload.timezone is not None:
        current_user.timezone = payload.timezone
    if payload.language is not None:
        current_user.language = payload.language
    if payload.locale is not None:
        current_user.locale = payload.locale
    if payload.date_format is not None:
        current_user.date_format = payload.date_format
    if payload.time_format is not None:
        current_user.time_format = payload.time_format
    if payload.number_format is not None:
        current_user.number_format = payload.number_format

    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)
    return current_user
