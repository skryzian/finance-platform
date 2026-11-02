from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    country: str = Field(default="KE", min_length=2, max_length=2)
    currency: str = Field(default="KES", min_length=3, max_length=3)
    timezone: str = Field(default="Africa/Nairobi", max_length=64)
    language: str = Field(default="en", min_length=2, max_length=10)
    locale: str = Field(default="en_KE", min_length=2, max_length=20)
    date_format: str = Field(default="DD/MM/YYYY", max_length=20)
    time_format: str = Field(default="24h", max_length=8)
    number_format: str = Field(default="#,##0.00", max_length=32)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    locale: str | None = Field(default=None, max_length=20)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserOut(UserBase):
    id: int
    profile_image_url: str | None = None
    profile_thumbnail_url: str | None = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=2048)


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    locale: str | None = Field(default=None, min_length=2, max_length=20)
    date_format: str | None = Field(default=None, max_length=20)
    time_format: str | None = Field(default=None, max_length=8)
    number_format: str | None = Field(default=None, max_length=32)


class ProfilePhotoUpload(BaseModel):
    image_url: str
    thumbnail_url: str
