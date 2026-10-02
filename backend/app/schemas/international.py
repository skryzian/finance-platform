from pydantic import BaseModel, Field


class CountryOut(BaseModel):
    id: int
    country_code: str
    alpha3: str
    country_name: str
    default_currency: str
    default_timezone: str
    locale: str
    phone_country_code: str
    active: bool

    model_config = {"from_attributes": True}


class CurrencyOut(BaseModel):
    id: int
    code: str
    currency_name: str
    symbol: str
    decimal_places: int
    active: bool

    model_config = {"from_attributes": True}


class UserInternationalSettings(BaseModel):
    country_code: str = Field(..., min_length=2, max_length=2)
    primary_currency: str = Field(..., min_length=3, max_length=3)
    timezone: str = Field(..., min_length=3)
    language: str = Field(default="en", min_length=2, max_length=10)
    locale: str = Field(..., min_length=2)
    date_format: str = Field(default="DD/MM/YYYY")
    time_format: str = Field(default="24h")
    number_format: str = Field(default="#,##0.00")


class UserInternationalSettingsOut(UserInternationalSettings):
    id: int
