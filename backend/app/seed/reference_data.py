from app.db.database import SessionLocal
from app.models.country import Country
from app.models.currency import Currency


def seed_reference_data() -> None:
    db = SessionLocal()
    try:
        countries = [
            Country(
                country_code="KE",
                alpha3="KEN",
                country_name="Kenya",
                default_currency="KES",
                default_timezone="Africa/Nairobi",
                locale="en_KE",
                phone_country_code="+254",
                active=True,
            ),
            Country(
                country_code="US",
                alpha3="USA",
                country_name="United States",
                default_currency="USD",
                default_timezone="America/New_York",
                locale="en_US",
                phone_country_code="+1",
                active=True,
            ),
            Country(
                country_code="GB",
                alpha3="GBR",
                country_name="United Kingdom",
                default_currency="GBP",
                default_timezone="Europe/London",
                locale="en_GB",
                phone_country_code="+44",
                active=True,
            ),
            Country(
                country_code="JP",
                alpha3="JPN",
                country_name="Japan",
                default_currency="JPY",
                default_timezone="Asia/Tokyo",
                locale="ja_JP",
                phone_country_code="+81",
                active=True,
            ),
        ]

        currencies = [
            Currency(code="KES", currency_name="Kenyan Shilling", symbol="KSh", decimal_places=2, active=True),
            Currency(code="USD", currency_name="US Dollar", symbol="$", decimal_places=2, active=True),
            Currency(code="EUR", currency_name="Euro", symbol="€", decimal_places=2, active=True),
            Currency(code="GBP", currency_name="Pound Sterling", symbol="£", decimal_places=2, active=True),
            Currency(code="JPY", currency_name="Japanese Yen", symbol="¥", decimal_places=0, active=True),
            Currency(code="ZAR", currency_name="South African Rand", symbol="R", decimal_places=2, active=True),
            Currency(code="UGX", currency_name="Ugandan Shilling", symbol="USh", decimal_places=0, active=True),
            Currency(code="TZS", currency_name="Tanzanian Shilling", symbol="TSh", decimal_places=0, active=True),
            Currency(code="NGN", currency_name="Nigerian Naira", symbol="₦", decimal_places=2, active=True),
            Currency(code="AED", currency_name="UAE Dirham", symbol="د.إ", decimal_places=2, active=True),
            Currency(code="CAD", currency_name="Canadian Dollar", symbol="C$", decimal_places=2, active=True),
            Currency(code="AUD", currency_name="Australian Dollar", symbol="A$", decimal_places=2, active=True),
            Currency(code="INR", currency_name="Indian Rupee", symbol="₹", decimal_places=2, active=True),
        ]

        for item in countries:
            existing = db.query(Country).filter(Country.country_code == item.country_code).first()
            if not existing:
                db.add(item)

        for item in currencies:
            existing = db.query(Currency).filter(Currency.code == item.code).first()
            if not existing:
                db.add(item)

        db.commit()
    finally:
        db.close()
